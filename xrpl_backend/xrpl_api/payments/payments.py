import logging
import time

from asgiref.sync import sync_to_async
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from xrpl import XRPLException
from xrpl.asyncio.account import get_balance, does_account_exist
from xrpl.asyncio.clients import AsyncWebsocketClient, XRPLRequestFailureException
from xrpl.asyncio.ledger import get_fee
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.core.addresscodec import XRPLAddressCodecException
from xrpl.models import AccountSetAsfFlag
from xrpl.utils import xrp_to_drops
from xrpl.wallet import Wallet
from django.apps import apps

from .payments_util import check_pay_channel_entries, create_payment_transaction, process_payment_response, \
    process_payment, get_account_reserves, check_account_ledger_entries, calculate_last_ledger_sequence
from ..accounts.account_utils import prepare_account_data, check_check_entries, \
    create_account_delete_transaction, account_delete_tx_response, prepare_regular_key, prepare_account_set_enabled_tx, \
    delete_account_response
from ..constants import ENTERING_FUNCTION_LOG, LEAVING_FUNCTION_LOG, INVALID_WALLET_IN_REQUEST, \
    SENDER_SEED_IS_INVALID, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, FAILED_TO_FETCH_RESERVE_DATA, \
    INSUFFICENT_BALANCE_TO_COVER_RESERVER_FEES, asfDisableMaster
from ..errors.error_handling import handle_error_new, error_response, process_transaction_error
from ..escrows.escrows_util import check_escrow_entries
from ..ledger.ledger_util import check_ripple_state_entries
from ..transactions.transactions_util import prepare_tx
from ..utils import is_valid_xrpl_seed, \
    total_execution_time_in_millis, validate_request_data, fetch_network_fee, \
    validate_xrp_wallet, validate_xrpl_response_data

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class SendXrpPaymentsAndDeleteAccount(View):

    async def post(self, request, *args, **kwargs):
        return await self.send_xrp_payment_and_delete_account(request)

    async def get(self, request, *args, **kwargs):
        return await self.send_xrp_payment_and_delete_account(request)

    async def send_xrp_payment_and_delete_account(self, request):
        start_time = time.time()
        function_name = "send_xrp_payment_and_delete_account"
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            account = self.request.GET['account']
            # Validate the provided wallet address
            if not account or not validate_xrp_wallet(account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            sender_seed = self.request.GET['sender_seed']
            if not is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            xrpl_config = apps.get_app_config('xrpl_api')
            async with AsyncWebsocketClient(xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL) as client:

                sender_wallet = Wallet.from_seed(sender_seed)

                check_account_ledger_entries_start_time = time.time()
                valid_address, account_objects = await check_account_ledger_entries(client, sender_wallet.classic_address)
                if not valid_address:
                    raise XRPLException(error_response("Wallet not found on ledger. Unable to delete wallet"))
                logger.info(f"await check_account_ledger_entries total time: {total_execution_time_in_millis(check_account_ledger_entries_start_time)}")

                account_info_request = prepare_account_data(sender_wallet.classic_address, False)

                # Check if there are any escrow, payment channels, Ripple state, or check entries
                # that prevent the wallet from being deleted.
                if not check_escrow_entries(account_objects):
                    raise XRPLException(error_response("Wallet has an escrow. Unable to delete wallet"))

                if not check_pay_channel_entries(account_objects):
                    raise XRPLException(error_response("Wallet has payment channels. Unable to delete wallet"))

                if not check_ripple_state_entries(account_objects):
                    raise XRPLException(error_response("Wallet has Ripple state entries. Unable to delete wallet"))

                if not check_check_entries(account_objects):
                    raise XRPLException("Wallet has check entries. Unable to delete wallet")

                account_info_response_start_time = time.time()
                account_info_response = await client.request(account_info_request)
                if validate_xrpl_response_data(account_info_response):
                    process_transaction_error(account_info_response)

                logger.info(f"await account_info_response total time: {total_execution_time_in_millis(account_info_response_start_time)}")

                balance = int(account_info_response.result['account_data']['Balance'])

                get_account_reserves_start_time = time.time()
                base_reserve, reserve_increment = await get_account_reserves(client)
                if base_reserve is None or reserve_increment is None:
                    raise XRPLException(error_response("Failed to retrieve reserve requirements from the XRPL."))
                logger.info(f"await get_account_reserves total time: {total_execution_time_in_millis(get_account_reserves_start_time)}")

                drops = xrp_to_drops(base_reserve)
                transferable_amount = int(balance) - int(drops)

                if transferable_amount <= 0:
                    raise XRPLException(error_response("Insufficient balance to cover the reserve and fees."))

                payment_tx = create_payment_transaction(sender_wallet.classic_address, account,
                                                        str(transferable_amount), str(0), True)

                process_payment_start_time = time.time()
                payment_response = await process_payment(payment_tx, client, sender_wallet)
                if validate_xrpl_response_data(payment_response):
                    process_transaction_error(payment_response)

                logger.info(f"await process_payment total time: {total_execution_time_in_millis(process_payment_start_time)}")

                calculate_last_ledger_sequence_start_time = time.time()
                last_ledger_sequence = await calculate_last_ledger_sequence(client, buffer_time=10)
                logger.info(
                    f"await calculate_last_ledger_sequence total time: {total_execution_time_in_millis(calculate_last_ledger_sequence_start_time)}")

                account_delete_tx = create_account_delete_transaction(sender_wallet.classic_address, account,
                                                                      last_ledger_sequence)

                process_payment_sequence_start_time = time.time()
                account_delete_response = await process_payment(account_delete_tx, client, sender_wallet)
                if validate_xrpl_response_data(account_delete_response):
                    process_transaction_error(account_delete_response)

                logger.info(f"await process_payment total time: {total_execution_time_in_millis(process_payment_sequence_start_time)}")

                return account_delete_tx_response(account_delete_response, payment_response)
        except (XRPLRequestFailureException, XRPLException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

@method_decorator(csrf_exempt, name="dispatch")
class SendXrpPayments(View):

    async def post(self, request, *args, **kwargs):
        return await self.send_xrp_payment(request)

    async def get(self, request, *args, **kwargs):
        return await self.send_xrp_payment(request)

    async def send_xrp_payment(self, request):
        start_time = time.time()
        function_name = 'send_xrp_payment'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            sender_seed = self.request.GET['sender_seed']
            receiver_account = self.request.GET['receiver_account']
            amount_xrp = self.request.GET['amount_xrp']

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
                logger.info(f"Sender Address Balance: { await get_balance(sender_address, client)}")
                logger.info(f"Receiver Address Balance: {await get_balance(receiver_account, client)}")

                fee_drops = await fetch_network_fee(client)
                logger.info(f"fee_drops: {fee_drops}")

                payment_transaction = create_payment_transaction(sender_address, receiver_account, str(amount_drops), str(fee_drops), False)

                process_payment_start_time = time.time()
                payment_response = await process_payment(payment_transaction, client, sender_wallet)
                logger.info(f"await process_payment total time: {total_execution_time_in_millis(process_payment_start_time)}")

                # Validate client response. Raise exception on error
                if validate_xrpl_response_data(payment_response):
                    process_transaction_error(payment_response)

                # Create a Transaction request to see transaction
                tx_response = await client.request(prepare_tx(payment_response.result["hash"]))

                # Check balances after 1000 was sent from wallet1 to wallet2
                logger.info("Balances of wallets after Payment tx:")
                logger.info(f"Sender Address Balance: {await get_balance(sender_address, client)}")
                logger.info(f"Receiver Address Balance: {await get_balance(receiver_account, client)}")

                logger.debug("payment_response:")
                # logger.debug(json.dumps(result, indent=4, sort_keys=True))

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
class SendXrpPaymentAndBlackHoleAccount(View):

    async def post(self, request, *args, **kwargs):
        return await self.send_xrp_payment_and_black_hole_account(request)

    async def get(self, request, *args, **kwargs):
        return await self.send_xrp_payment_and_black_hole_account(request)

    async def send_xrp_payment_and_black_hole_account(self, request):
        start_time = time.time()  # Capture the start time
        function_name = 'black_hole_xrp'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering function

        try:
            receiving_account = self.request.GET['receiving_account']
            sender_seed = self.request.GET['sender_seed']

            if not is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            # Get black hole address from the environment configuration.s
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

                # Send the request to the XRPL client
                account_info_response = await client.request(account_info)

                if validate_xrpl_response_data(account_info_response):
                    process_transaction_error(account_info_response)

                balance = int(account_info_response.result['account_data']['Balance'])
                base_reserve, reserve_increment = await get_account_reserves(client)
                if base_reserve is None or reserve_increment is None:
                    raise XRPLException(error_response(FAILED_TO_FETCH_RESERVE_DATA.format(receiving_account)))

                drops = xrp_to_drops(base_reserve)
                transferable_amount = int(balance) - int(drops)

                if transferable_amount <= 0:
                    raise XRPLException(error_response(INSUFFICENT_BALANCE_TO_COVER_RESERVER_FEES))

                fee_drops = await get_fee(client)

                payment_tx = create_payment_transaction(wallet.classic_address, receiving_account, str(transferable_amount), fee_drops, False)
                payment_tx_response = await submit_and_wait(payment_tx, client, wallet)

                if validate_xrpl_response_data(payment_tx_response):
                    process_transaction_error(payment_tx_response)

                # Prepare and send request to get the account info from the ledger.
                account_info = prepare_account_data(receiving_account, True)
                account_info_response = await client.request(account_info)

                if validate_xrpl_response_data(account_info_response):
                    process_transaction_error(account_info_response)

                # Prepare a transaction to set the account's regular key to the black hole address.
                tx_regular_key = prepare_regular_key(wallet.classic_address, xrpl_config.BLACK_HOLE_ADDRESS)

                submit_tx_regular = await submit_and_wait(transaction=tx_regular_key, client=client, wallet=wallet)
                if validate_xrpl_response_data(submit_tx_regular):
                    process_transaction_error(submit_tx_regular)

                tx_response = await client.request(prepare_tx(submit_tx_regular.result["hash"]))
                if validate_xrpl_response_data(tx_response):
                    process_transaction_error(tx_response)

                # Prepare a transaction to disable the master key on the account.
                tx_disable_master_key = prepare_account_set_enabled_tx(wallet.classic_address, AccountSetAsfFlag.ASF_DISABLE_MASTER)

                submit_tx_disable = await submit_and_wait(transaction=tx_disable_master_key, client=client, wallet=wallet)
                if validate_xrpl_response_data(submit_tx_disable):
                    process_transaction_error(submit_tx_disable)

                tx_response = await client.request(prepare_tx(submit_tx_disable.result["hash"]))
                if validate_xrpl_response_data(tx_response):
                    process_transaction_error(tx_response)

                # Prepare a request to check the account's flags after the transaction.
                get_acc_flag = prepare_account_data(wallet.classic_address, True)

                get_acc_flag_response = await client.request(get_acc_flag)
                if validate_xrpl_response_data(get_acc_flag_response):
                    process_transaction_error(get_acc_flag_response)

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
