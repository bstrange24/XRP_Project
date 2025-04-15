import asyncio
import json
import logging
import time

from asgiref.sync import sync_to_async
from django.apps import apps
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from xrpl import XRPLException
from xrpl.asyncio.account import get_balance, does_account_exist
from xrpl.asyncio.clients import AsyncWebsocketClient, XRPLRequestFailureException
from xrpl.asyncio.ledger import get_fee, get_latest_validated_ledger_sequence
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.core.addresscodec import XRPLAddressCodecException
from xrpl.models import AccountSetAsfFlag, Payment, IssuedCurrencyAmount
from xrpl.utils import xrp_to_drops, get_balance_changes, get_final_balances, drops_to_xrp
from xrpl.wallet import Wallet

from .payments_util import check_pay_channel_entries, create_payment_transaction, process_payment_response, \
    process_payment, get_account_reserves, check_account_ledger_entries, save_account_delete_tx_response, \
    create_payment_transaction_with_memo
from ..accounts.account_utils import prepare_account_data, check_check_entries, \
    create_account_delete_transaction, prepare_regular_key, prepare_account_set_enabled_tx, \
    delete_account_response, check_nfts_entries, check_signer_list, check_ticket_entries, check_for_unknown_entries, check_amm_entries
from ..constants.constants import ENTERING_FUNCTION_LOG, LEAVING_FUNCTION_LOG, INVALID_WALLET_IN_REQUEST, \
    SENDER_SEED_IS_INVALID, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, FAILED_TO_FETCH_RESERVE_DATA, \
    INSUFFICIENT_BALANCE_TO_COVER_RESERVER_FEES, asfDisableMaster
from ..errors.error_handling import handle_error_new, error_response, process_transaction_error, \
    process_unexpected_error
from ..escrows.escrows_util import check_escrow_entries
from ..ledger.ledger_util import check_ripple_state_entries
from ..transactions.transactions_util import prepare_tx
from ..utilities.base_xrpl_view import BaseXRPLView
from ..utilities.utilities import is_valid_xrpl_seed, \
    total_execution_time_in_millis, validate_request_data, fetch_network_fee, \
    validate_xrp_wallet, validate_xrpl_response_data, validate_response

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class SendMemePayments(BaseXRPLView):
    async def post(self, request):
        return await self.send_meme_payment(request)

    async def get(self, request):
        return await self.send_meme_payment(request)

    async def send_meme_payment(self, request):
        start_time = time.time()
        function_name = 'send_xrp_payment'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Parse request body
            data = json.loads(request.body)
            issuer_seed = data.get("issuer_seed")  # Creator of the escrow
            destination_address = data.get("destination_address")  # Seed of the escrow creator
            source_currency = data.get("source_currency")  # Sequence number of the escrow create tx
            amount_to_deliver = data.get("amount_to_deliver")

            logger.info(f"Receiver account: {destination_address}")
            logger.info(f"Sending {amount_to_deliver} {source_currency}")

            xrpl_config = apps.get_app_config('xrpl_api')
            async with AsyncWebsocketClient(xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL) as client:
                issuer_wallet = Wallet.from_seed(issuer_seed)

                logger.info("Balances of wallets before Payment tx")
                logger.info(f"Sender Address Balance: {await get_balance(issuer_wallet.classic_address, client)}")
                logger.info(f"Receiver Address Balance: {await get_balance(destination_address, client)}")

                payment_transaction = Payment(
                    account=issuer_wallet.classic_address,
                    destination=destination_address,
                    amount=IssuedCurrencyAmount(
                        currency=source_currency,
                        issuer=issuer_wallet.classic_address,
                        value=str(amount_to_deliver)
                    ),
                    send_max=IssuedCurrencyAmount(  # Specify the max amount the sender is willing to send
                        currency=source_currency,
                        issuer=issuer_wallet.classic_address,
                        value=str(float(amount_to_deliver) * 1.05)  # Allowing 5% slippage
                    ),
                    flags=0x00020000  # tfPartialPayment flag
                )

                process_payment_start_time = time.time()
                try:
                    payment_response = await process_payment(payment_transaction, client, issuer_wallet)
                    validate_response(payment_response, f"Send {source_currency} payment error")
                    logger.info(f"await process_payment total time: {total_execution_time_in_millis(process_payment_start_time)}")
                except Exception as e:
                    raise XRPLException({str(e)})

                # Create a Transaction request to see transaction
                tx_response = await client.request(prepare_tx(payment_response.result["hash"]))

                # Check balances after 1000 was sent from wallet1 to wallet2
                logger.info("Balances of wallets after Payment tx:")
                logger.info(f"Sender Address Balance: {await get_balance(issuer_wallet.classic_address, client)}")
                logger.info(f"Receiver Address Balance: {await get_balance(destination_address, client)}")
                logger.info(f"Get balance changes: {get_balance_changes(tx_response.result['meta'])}")
                logger.info(f"Get final balances: {get_final_balances(tx_response.result['meta'])}")

                return JsonResponse({
                    "result": payment_response.result
                })

        except (XRPLRequestFailureException, XRPLException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

@method_decorator(csrf_exempt, name="dispatch")
class SendXrpPaymentsAndDeleteAccount(BaseXRPLView):

    async def post(self, request):
        return await self.send_xrp_payment_and_delete_account(request)

    async def get(self, request):
        return await self.send_xrp_payment_and_delete_account(request)

    async def send_xrp_payment_and_delete_account(self, request):
        start_time = time.time()
        function_name = "send_xrp_payment_and_delete_account"
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            data = json.loads(request.body)
            account = data.get("account")
            if not account or not validate_xrp_wallet(account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            sender_seed = data.get("sender_seed")
            if not is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            xrpl_config = apps.get_app_config('xrpl_api')
            async with AsyncWebsocketClient(xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL) as client:

                if not await does_account_exist(account, client):
                    raise XRPLException(f"Destination account {account} does not exist on the ledger")

                sender_wallet = Wallet.from_seed(sender_seed)

                # Check account and objects
                valid_address, account_objects = await check_account_ledger_entries(client, sender_wallet.classic_address)
                if not valid_address:
                    raise XRPLException(error_response("Wallet not found on ledger. Unable to delete wallet"))
                if not check_escrow_entries(account_objects):
                    raise XRPLException(error_response("Wallet has an escrow. Unable to delete wallet"))
                if not check_pay_channel_entries(account_objects):
                    raise XRPLException(error_response("Wallet has payment channels. Unable to delete wallet"))
                if not check_ripple_state_entries(account_objects):
                    raise XRPLException(error_response("Wallet has Ripple state entries. Unable to delete wallet"))
                if not check_check_entries(account_objects):
                    raise XRPLException(error_response("Wallet has check entries. Unable to delete wallet"))
                if not check_nfts_entries(account_objects):
                    raise XRPLException(error_response("Wallet has NFT entries. Unable to delete wallet"))
                if not check_signer_list(account_objects):
                    raise XRPLException(error_response("Wallet has Signer List entries. Unable to delete wallet"))
                if not check_ticket_entries(account_objects):
                    raise XRPLException(error_response("Wallet has Ticket entries. Unable to delete wallet"))
                if not check_amm_entries(account_objects):
                    raise XRPLException(error_response("Wallet has AMM entries. Unable to delete wallet"))

                check_for_unknown_entries(account_objects)

                # Fetch balance
                account_info_request = prepare_account_data(sender_wallet.classic_address, False)
                account_info_response = await client.request(account_info_request)
                validate_response(account_info_response, f"Getting account info error")

                flags = account_info_response.result["account_data"]["Flags"]
                if flags & asfDisableMaster:  # Assuming asfDisableMaster is defined
                    logger.info("Master key disabled")
                    raise XRPLException("Cannot delete account with disabled master key unless regular key is provided")

                sequence = account_info_response.result["account_data"]["Sequence"]
                current_ledger = await get_latest_validated_ledger_sequence(client)
                if current_ledger - sequence < 256:
                    logger.info(f"Account too recent: Sequence {sequence}, Current ledger {current_ledger}")
                    raise XRPLException("Account is too recent to delete (must be at least 256 ledgers old)")

                owner_count = account_info_response.result["account_data"]["OwnerCount"]
                if owner_count != 0:
                    logger.warning(f"OwnerCount is {owner_count}, but no objects found in account_objects")
                    raise XRPLException("Account has non-zero OwnerCount. Unable to delete wallet")

                # Calculate reserves
                base_reserve, reserve_increment = await get_account_reserves(client)
                if base_reserve is None or reserve_increment is None:
                    raise XRPLException(error_response("Failed to retrieve reserve requirements from the XRPL."))

                # Verify no objects for safety
                number_of_objects = len(account_objects)
                total_reserve = base_reserve + (reserve_increment * number_of_objects)
                if number_of_objects > 0:
                    raise XRPLException(error_response("Unexpected objects found. Unable to delete wallet."))

                balance = int(account_info_response.result['account_data']['Balance'])
                transferable_amount = int(balance) - int(xrp_to_drops(total_reserve))
                if transferable_amount <= 0:
                    raise XRPLException(error_response("Insufficient balance to cover the reserve and fees."))

                # Send payment
                fee_drops = await get_fee(client)
                last_ledger_sequence = await get_latest_validated_ledger_sequence(client) + 50
                payment_tx = create_payment_transaction(sender_wallet.classic_address, account, str(transferable_amount), str(fee_drops), True, last_ledger_sequence)
                payment_response = await process_payment(payment_tx, client, sender_wallet)
                validate_response(payment_response, f"Error sending payment")

                # Wait for payment confirmation
                while True:
                    tx_response = await client.request(prepare_tx(payment_response.result["hash"]))
                    if tx_response.result.get("validated"):
                        break
                    await asyncio.sleep(1)

                # Delete account
                last_ledger_sequence = await get_latest_validated_ledger_sequence(client) + 50
                account_delete_tx = create_account_delete_transaction(sender_wallet.classic_address, account, last_ledger_sequence)
                account_delete_response = await process_payment(account_delete_tx, client, sender_wallet)
                validate_response(payment_response, f"Error deleting account")

                # Log final state
                logger.info(f"Payment balance changes: {json.dumps(get_balance_changes(payment_response.result['meta']))}")
                logger.info(f"Payment final balances: {json.dumps(get_final_balances(payment_response.result['meta']))}")
                logger.info(f"Deletion balance changes: {json.dumps(get_balance_changes(account_delete_response.result['meta']))}")
                logger.info(f"Deletion final balances: {json.dumps(get_final_balances(account_delete_response.result['meta']))}")
                logger.info(f"Note: {xrp_to_drops(2)} drops were consumed as a deletion fee.")

                return await sync_to_async(save_account_delete_tx_response, thread_sensitive=True)(
                    account_delete_response, payment_response, sender_wallet.classic_address, account,
                    transferable_amount, xrp_to_drops(total_reserve)
                )

        except (XRPLRequestFailureException, XRPLException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

@method_decorator(csrf_exempt, name="dispatch")
class SendXrpPayments(BaseXRPLView):

    async def post(self, request):
        return await self.send_xrp_payment(request)

    async def get(self, request):
        return await self.send_xrp_payment(request)

    async def send_xrp_payment(self, request):
        start_time = time.time()
        function_name = 'send_xrp_payment'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Parse request body
            data = json.loads(request.body)
            sender_seed = data.get("sender_seed")  # Creator of the escrow
            receiver_account = data.get("receiver_account")  # Seed of the escrow creator
            amount_xrp = data.get("amount_xrp")  # Sequence number of the escrow create tx
            memo_data = data.get("memo_data", None)
            memo_type = data.get("memo_type", None)
            memo_format = data.get("memo_format", None)

            validate_request_data(sender_seed, receiver_account, amount_xrp)

            logger.info(f"Receiver account: {receiver_account}")
            logger.info(f"Sending {amount_xrp} XRP")

            amount_drops = xrp_to_drops(float(amount_xrp))
            logger.info(f"Amount in drops: {amount_drops}")

            xrpl_config = apps.get_app_config('xrpl_api')
            async with AsyncWebsocketClient(xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL) as client:
                sender_wallet = Wallet.from_seed(sender_seed)
                sender_address = sender_wallet.classic_address

                logger.info("Balances of wallets before Payment tx")
                logger.info(f"Sender Address Balance: {await get_balance(sender_address, client)}")
                logger.info(f"Receiver Address Balance: {await get_balance(receiver_account, client)}")

                fee_drops = await fetch_network_fee(client)
                logger.info(f"fee_drops: {fee_drops}")
                last_ledger_sequence = await get_latest_validated_ledger_sequence(client)

                if memo_data is not None and memo_type is not None and memo_format is not None:
                    memo_data = memo_data.encode('utf-8').hex()
                    memo_type = memo_type.encode('utf-8').hex()
                    memo_format = memo_format.encode('utf-8').hex()
                    payment_transaction = create_payment_transaction_with_memo(sender_address, receiver_account, str(amount_drops), str(fee_drops),memo_data, memo_type, memo_format, last_ledger_sequence)
                else:
                    payment_transaction = create_payment_transaction(sender_address, receiver_account, str(amount_drops), str(fee_drops), False, last_ledger_sequence)

                process_payment_start_time = time.time()
                payment_response = await process_payment(payment_transaction, client, sender_wallet)
                validate_response(payment_response, "Send XRP payment error")
                logger.info(f"await process_payment total time: {total_execution_time_in_millis(process_payment_start_time)}")

                # Create a Transaction request to see transaction
                tx_response = await client.request(prepare_tx(payment_response.result["hash"]))

                # Check balances after 1000 was sent from wallet1 to wallet2
                logger.info("Balances of wallets after Payment tx:")
                logger.info(f"Sender Address Balance: {await get_balance(sender_address, client)}")
                logger.info(f"Receiver Address Balance: {await get_balance(receiver_account, client)}")
                logger.info(f"Get balance changes: {get_balance_changes(tx_response.result['meta'])}")
                logger.info(f"Get final balances: {get_final_balances(tx_response.result['meta'])}")

                # Handle the transaction response
                # Use `sync_to_async` to handle database operations asynchronously
                # Always await coroutines in asynchronous code.
                return await sync_to_async(process_payment_response, thread_sensitive=True)(
                    tx_response, payment_response, sender_address, receiver_account, amount_xrp, str(fee_drops)
                )
        except (XRPLRequestFailureException, XRPLException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

@method_decorator(csrf_exempt, name="dispatch")
class SendXrpPaymentAndBlackHoleAccount(BaseXRPLView):

    async def post(self, request):
        return await self.send_xrp_payment_and_black_hole_account(request)

    async def get(self, request):
        return await self.send_xrp_payment_and_black_hole_account(request)

    async def send_xrp_payment_and_black_hole_account(self, request):
        start_time = time.time()  # Capture the start time
        function_name = 'black_hole_xrp'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering function

        try:
            # Parse request body
            data = json.loads(request.body)
            receiving_account = data.get("receiving_account")  # Creator of the escrow
            sender_seed = data.get("sender_seed")  # Seed of the escrow creator

            if not is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            # Get black hole address from the environment configurations
            xrpl_config = apps.get_app_config('xrpl_api')

            if not receiving_account:
                receiving_account = xrpl_config.BLACK_HOLE_ADDRESS
                logger.info(f"Receiving account is {receiving_account}. We are sending the accounts XRP to a black hole address")
            else:
                logger.info(f"Receiving account is {receiving_account}. We are not sending the accounts XRP to a black hole address")
                if not validate_xrp_wallet(receiving_account):
                    raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))

            async with AsyncWebsocketClient(xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL) as client:

                if not await does_account_exist(receiving_account, client):
                    raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(receiving_account)))

                wallet = Wallet.from_seed(sender_seed)

                # Prepare account data for the request
                account_info = prepare_account_data(wallet.classic_address, False)
                account_info_response = await client.request(account_info)
                validate_response(account_info_response, "Account info error")

                balance = int(account_info_response.result['account_data']['Balance'])
                base_reserve, reserve_increment = await get_account_reserves(client)
                if base_reserve is None or reserve_increment is None:
                    raise XRPLException(error_response(FAILED_TO_FETCH_RESERVE_DATA.format(receiving_account)))

                logger.info(f"Base reserver: {base_reserve} Reserver increment: {reserve_increment}")

                drops = xrp_to_drops(base_reserve)
                transferable_amount = int(balance) - int(drops)
                logger.info(f"Base reserver in drops: {drops_to_xrp(str(drops))} Transferable XRP amount: {drops_to_xrp(str(transferable_amount))}")

                if transferable_amount <= 0:
                    raise XRPLException(error_response(INSUFFICIENT_BALANCE_TO_COVER_RESERVER_FEES))

                fee_drops = await get_fee(client)
                last_ledger_sequence = await get_latest_validated_ledger_sequence(client)
                logger.info(f"Network fees in drops {fee_drops} and in XRP: {drops_to_xrp(str(fee_drops))} Last ledger sequence: {last_ledger_sequence}")

                payment_tx = create_payment_transaction(wallet.classic_address, receiving_account,str(transferable_amount), fee_drops, False, last_ledger_sequence)
                logger.debug(f"payment_tx: {payment_tx}")
                logger.info("signing and submitting the transaction, awaiting a response")
                payment_tx_response = await submit_and_wait(payment_tx, client, wallet)
                logger.debug(f"payment_tx_response: {payment_tx_response}")
                validate_response(payment_tx_response, "Send XRP payment error")

                # Prepare and send request to get the account info from the ledger.
                account_info = prepare_account_data(receiving_account, True)
                account_info_response = await client.request(account_info)
                validate_response(account_info_response, "Getting account info error")

                # Prepare a transaction to set the account's regular key to the black hole address.
                tx_regular_key = prepare_regular_key(wallet.classic_address, xrpl_config.BLACK_HOLE_ADDRESS)
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_tx_regular = await submit_and_wait(transaction=tx_regular_key, client=client, wallet=wallet)
                validate_response(submit_tx_regular, "Tx Regular key error")

                tx_response = await client.request(prepare_tx(submit_tx_regular.result["hash"]))
                validate_response(tx_response, "Tx hash key error")

                # Prepare a transaction to disable the master key on the account.
                tx_disable_master_key = prepare_account_set_enabled_tx(wallet.classic_address,AccountSetAsfFlag.ASF_DISABLE_MASTER)
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_tx_disable = await submit_and_wait(transaction=tx_disable_master_key, client=client,wallet=wallet)
                validate_response(submit_tx_disable, "Disable master key error")

                tx_response = await client.request(prepare_tx(submit_tx_disable.result["hash"]))
                validate_response(tx_response, "Tx hash key error")

                # Prepare a request to check the account's flags after the transaction.
                get_acc_flag = prepare_account_data(wallet.classic_address, True)
                get_acc_flag_response = await client.request(get_acc_flag)
                validate_response(get_acc_flag_response, "Account flag error")

                logger.info(f"Get balance changes: {get_balance_changes(payment_tx_response.result['meta'])}")
                logger.info(f"Get final balances: {get_final_balances(payment_tx_response.result['meta'])}")

                # Verify if the master key has been successfully disabled.
                if get_acc_flag_response.result['account_data']['Flags'] == asfDisableMaster:
                    logger.info(f"Account {wallet.classic_address}'s master key has been disabled, account is black holed.")
                    logger.info(f"Account {wallet.classic_address}'s sent all of it's XRP to {receiving_account}.")
                else:
                    logger.info(f"Account {wallet.classic_address}'s master key is still enabled, account is NOT black holed")

                # Return the response indicating the account status after the operation.
                return delete_account_response(get_acc_flag_response)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
