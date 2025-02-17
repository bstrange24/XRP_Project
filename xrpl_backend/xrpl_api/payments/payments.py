import json
import logging
import time

from asgiref.sync import sync_to_async
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.utils import xrp_to_drops
from xrpl.wallet import Wallet
from django.apps import apps

from .payments_util import check_pay_channel_entries, create_payment_transaction, process_payment_response, \
    process_payment, get_account_reserves, check_account_ledger_entries, calculate_last_ledger_sequence
from ..accounts.account_utils import prepare_account_data, check_check_entries, \
    create_account_delete_transaction, account_delete_tx_response
from ..constants import ENTERING_FUNCTION_LOG, LEAVING_FUNCTION_LOG, XRPL_RESPONSE, ACCOUNT_IS_REQUIRED
from ..escrows.escrows_util import check_escrow_entries
from ..ledger.ledger_util import check_ripple_state_entries
from ..utils import is_valid_xrpl_seed, handle_error, \
    total_execution_time_in_millis, validate_request_data, fetch_network_fee, validate_xrpl_response

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class Payments(View):

    async def post(self, request, *args, **kwargs):
        return await self.send_payment_and_delete_account(request)

    async def get(self, request, *args, **kwargs):
        return await self.send_payment_and_delete_account(request)

    async def send_payment_and_delete_account(self, request):
        start_time = time.time()
        function_name = "send_payment_and_delete_account"
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            wallet_address = self.request.GET['account']
            if not wallet_address:
                raise ValueError(ACCOUNT_IS_REQUIRED)

            sender_seed = self.request.GET['sender_seed']
            if not is_valid_xrpl_seed(sender_seed):
                raise ValueError('Sender seed is invalid.')

            xrpl_config = apps.get_app_config('xrpl_api')
            async with AsyncWebsocketClient(xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL) as client:

                sender_wallet = Wallet.from_seed(sender_seed)

                check_account_ledger_entries_start_time = time.time()
                valid_address, account_objects = await check_account_ledger_entries(client,
                                                                                    sender_wallet.classic_address)
                if not valid_address:
                    raise ValueError("Wallet not found on ledger. Unable to delete wallet")
                logger.info(
                    f"await check_account_ledger_entries total time: {total_execution_time_in_millis(check_account_ledger_entries_start_time)}")

                account_info_request = prepare_account_data(sender_wallet.classic_address, False)

                # Check if there are any escrow, payment channels, Ripple state, or check entries
                # that prevent the wallet from being deleted.
                if not check_escrow_entries(account_objects):
                    raise ValueError("Wallet has an escrow. Unable to delete wallet")

                if not check_pay_channel_entries(account_objects):
                    raise ValueError("Wallet has payment channels. Unable to delete wallet")

                if not check_ripple_state_entries(account_objects):
                    raise ValueError("Wallet has Ripple state entries. Unable to delete wallet")

                if not check_check_entries(account_objects):
                    raise ValueError("Wallet has check entries. Unable to delete wallet")

                account_info_response_start_time = time.time()
                account_info_response = await client.request(account_info_request)
                is_valid, result = validate_xrpl_response(account_info_response, required_keys=["validated"])
                if not is_valid:
                    raise Exception(result)
                logger.info(
                    f"await account_info_response total time: {total_execution_time_in_millis(account_info_response_start_time)}")

                logger.debug("account_info_response:")
                logger.debug(json.dumps(result, indent=4, sort_keys=True))

                balance = int(account_info_response.result['account_data']['Balance'])

                get_account_reserves_start_time = time.time()
                base_reserve, reserve_increment = await get_account_reserves(client)
                if base_reserve is None or reserve_increment is None:
                    raise ValueError("Failed to retrieve reserve requirements from the XRPL.")
                logger.info(
                    f"await get_account_reserves total time: {total_execution_time_in_millis(get_account_reserves_start_time)}")

                drops = xrp_to_drops(base_reserve)
                transferable_amount = int(balance) - int(drops)

                if transferable_amount <= 0:
                    raise ValueError("Insufficient balance to cover the reserve and fees.")

                payment_tx = create_payment_transaction(sender_wallet.classic_address, wallet_address,
                                                        str(transferable_amount), str(0), True)

                process_payment_start_time = time.time()
                payment_response = await process_payment(payment_tx, client, sender_wallet)
                is_valid, payment_response_result = validate_xrpl_response(payment_response,
                                                                           required_keys=["validated"])
                if not is_valid:
                    raise Exception(payment_response_result)
                logger.info(
                    f"await process_payment total time: {total_execution_time_in_millis(process_payment_start_time)}")

                logger.debug("payment_response:")
                logger.debug(json.dumps(payment_response_result, indent=4, sort_keys=True))

                calculate_last_ledger_sequence_start_time = time.time()
                last_ledger_sequence = await calculate_last_ledger_sequence(client, buffer_time=10)
                logger.info(
                    f"await calculate_last_ledger_sequence total time: {total_execution_time_in_millis(calculate_last_ledger_sequence_start_time)}")

                account_delete_tx = create_account_delete_transaction(sender_wallet.classic_address, wallet_address,
                                                                      last_ledger_sequence)

                process_payment_sequence_start_time = time.time()
                account_delete_response = await process_payment(account_delete_tx, client, sender_wallet)
                is_valid, account_delete_response_result = validate_xrpl_response(account_delete_response,
                                                                                  required_keys=["validated"])
                if not is_valid:
                    raise Exception(account_delete_response_result)
                logger.info(
                    f"await process_payment total time: {total_execution_time_in_millis(process_payment_sequence_start_time)}")

                logger.debug("account_delete_response_result:")
                logger.debug(json.dumps(account_delete_response_result, indent=4, sort_keys=True))

                return account_delete_tx_response(account_delete_response_result, payment_response_result)
        except Exception as e:
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class SendPayments(View):

    async def post(self, request, *args, **kwargs):
        return await self.send_payment(request)

    async def get(self, request, *args, **kwargs):
        return await self.send_payment(request)

    async def send_payment(self, request):
        start_time = time.time()
        function_name = 'send_payment'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            sender_seed = self.request.GET['sender_seed']
            receiver_address = self.request.GET['receiver_address']
            amount_xrp = self.request.GET['amount_xrp']
            validate_request_data(sender_seed, receiver_address, amount_xrp)
            logger.info(f"Receiver account: {receiver_address}")
            logger.info(f"Sending {amount_xrp} XRP")

            amount_drops = xrp_to_drops(float(amount_xrp))
            logger.info(f"Amount in drops: {amount_drops}")

            xrpl_config = apps.get_app_config('xrpl_api')
            async with AsyncWebsocketClient(xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL) as client:
                sender_wallet = Wallet.from_seed(sender_seed)
                sender_address = sender_wallet.classic_address

                fee_drops = await fetch_network_fee(client)

                payment_transaction = create_payment_transaction(sender_address, receiver_address, str(amount_drops),
                                                                 str(fee_drops), False)

                process_payment_start_time = time.time()
                payment_response = await process_payment(payment_transaction, client, sender_wallet)
                logger.info(
                    f"await process_payment total time: {total_execution_time_in_millis(process_payment_start_time)}")

                is_valid, result = validate_xrpl_response(payment_response, required_keys=["validated"])
                if not is_valid:
                    raise Exception(result)

                logger.debug("payment_response:")
                logger.debug(json.dumps(result, indent=4, sort_keys=True))

                # Handle the transaction response
                # Use `sync_to_async` to handle database operations asynchronously
                return await sync_to_async(process_payment_response, thread_sensitive=True)(
                    result, payment_response, sender_address, receiver_address, amount_xrp, str(fee_drops)
                )

        except Exception as e:
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
