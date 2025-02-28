import hashlib
import logging
import time
from decimal import Decimal

from django.apps import apps
from django.core.exceptions import MultipleObjectsReturned
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.clients import XRPLRequestFailureException
from xrpl.core.addresscodec import XRPLAddressCodecException
from xrpl.ledger import get_latest_validated_ledger_sequence
from xrpl.models import Ledger, Fee, AccountInfo, AccountObjects, Tx
from xrpl.transaction import submit_and_wait
from xrpl.utils import drops_to_xrp, ripple_time_to_datetime
from xrpl.wallet import Wallet
from xrpl.utils import datetime_to_ripple_time

from .db_operations.escrow_db_operations import save_create_escrow_response
from .escrows_util import create_escrow_account_transaction, \
    create_cancel_escrow_transaction, create_finish_escrow_transaction, get_escrow_account_response, \
    get_escrow_tx_id_account_response, generate_escrow_condition_and_fulfillment, create_escrow_account_response, \
    create_escrow_transaction_with_finsh_cancel, set_claim_date, create_escrow_sequence_number_response, \
    get_escrow_sequence, create_escrow_cancel_response, create_finish_escrow_response, get_escrow_data_from_db
from ..constants.constants import ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, INVALID_WALLET_IN_REQUEST, \
    ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, SENDER_SEED_IS_INVALID, MISSING_REQUEST_PARAMETERS, INVALID_TX_ID_IN_REQUEST
from ..errors.error_handling import process_transaction_error, handle_error_new, error_response
from ..transactions.transactions_util import prepare_tx
from ..utilities.utilities import get_xrpl_client, \
    total_execution_time_in_millis, validate_xrp_wallet, is_valid_xrpl_seed, validate_xrpl_response_data, \
    is_valid_txn_id_format, does_txn_exist, count_xrp_received

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class GetEscrowAccountInfo(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.get_account_escrow_info(request)

    def get(self, request, *args, **kwargs):
        return self.get_account_escrow_info(request)

    def get_account_escrow_info(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'get_account_escrow_info'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        get_escrow_from_account = False
        get_escrow_from_txn_id = False

        try:
            escrow_account = self.request.GET.get('escrow_account')
            tx_hash = self.request.GET.get('tx_hash')

            # Check if both parameters are missing
            if not escrow_account and not tx_hash:
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            # Validate account if provided
            if escrow_account:
                if not validate_xrp_wallet(escrow_account):
                    raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))
                if not does_account_exist(escrow_account, self.client):
                    raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(escrow_account)))

            # Set flags based on parameters
            if tx_hash and not escrow_account:
                get_escrow_from_txn_id = True
            elif escrow_account and not tx_hash:
                get_escrow_from_account = True
            else:
                # If both parameters are provided, prioritize `account` over `prev_txn_id`
                get_escrow_from_account = True

            if get_escrow_from_txn_id and (not is_valid_txn_id_format(tx_hash) or not does_txn_exist(tx_hash, self.client)):
                raise XRPLException(error_response(INVALID_TX_ID_IN_REQUEST))

            if get_escrow_from_account:
                logger.info(f"Getting escrow based on account: {get_escrow_from_account}")
                all_escrows_dict = {}
                sent_escrows = []
                received_escrows = []

                # Build and make request
                escrow_account_request = create_escrow_account_transaction(escrow_account)
                escrow_account_response = self.client.request(escrow_account_request)

                # Validate client response. Raise exception on error
                if validate_xrpl_response_data(escrow_account_response):
                    process_transaction_error(escrow_account_response)

                # Return account escrows
                escrows = escrow_account_response.result["account_objects"]

                # Loop through result and parse account escrows
                for escrow in escrows:
                    escrow_data = {}
                    if isinstance(escrow["Amount"], str):
                        escrow_data["escrow_id"] = escrow["index"]
                        escrow_data["sender"] = escrow["Account"]
                        escrow_data["receiver"] = escrow["Destination"]
                        escrow_data["amount"] = str(drops_to_xrp(escrow["Amount"]))
                        if "PreviousTxnID" in escrow:
                            escrow_data["prex_txn_id"] = escrow["PreviousTxnID"]
                        if "FinishAfter" in escrow:
                            escrow_data["redeem_date"] = str(ripple_time_to_datetime(escrow["FinishAfter"]))
                        if "CancelAfter" in escrow:
                            escrow_data["expiry_date"] = str(ripple_time_to_datetime(escrow["CancelAfter"]))
                        if "Condition" in escrow:
                            escrow_data["condition"] = escrow["Condition"]

                        # Sort escrows
                        if escrow_data["sender"] == escrow_account:
                            sent_escrows.append(escrow_data)
                        else:
                            received_escrows.append(escrow_data)

                # Add lists to escrow dict
                all_escrows_dict["sent"] = sent_escrows
                all_escrows_dict["received"] = received_escrows

                return get_escrow_account_response(all_escrows_dict)
            else:
                logger.info(f"Getting escrow based on txn id: {tx_hash}")
                # Build and send query for PreviousTxnID
                transaction_id_request = prepare_tx(tx_hash)
                transaction_id_response = self.client.request(transaction_id_request)

                # Validate client response. Raise exception on error
                if validate_xrpl_response_data(transaction_id_response):
                    process_transaction_error(transaction_id_response)

                if "Sequence" not in transaction_id_response:
                    raise XRPLException(error_response("EscrowCreate transaction not found or invalid."))

                # Return the result
                result = transaction_id_response.result

                # Print escrow sequence if available
                if "Sequence" in result:
                    logger.info(f'escrow sequence: {result["Sequence"]}')
                # Use escrow ticket sequence if escrow sequence is not available
                if "TicketSequence" in result:
                    logger.info(f'escrow ticket sequence: {result["TicketSequence"]}')

                return get_escrow_tx_id_account_response(result)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class CreateEscrow(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.create_account_escrow(request)

    def get(self, request, *args, **kwargs):
        return self.create_account_escrow(request)

    def create_account_escrow(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'create_account_escrow'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            escrow_account = self.request.GET.get('escrow_account')
            escrow_creator_seed = self.request.GET.get('escrow_creator_seed')
            amount_to_escrow = self.request.GET.get('amount_to_escrow')
            finish_after_time = self.request.GET.get('finish_after_time')
            cancel_after_time = self.request.GET.get('cancel_after_time')

            if not all([escrow_account, escrow_creator_seed, amount_to_escrow]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(escrow_creator_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not escrow_account and not validate_xrp_wallet(escrow_account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            if not does_account_exist(escrow_account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(escrow_account)))

            xrpl_config = apps.get_app_config('xrpl_api')

            # Get the ledger details
            ledger_response = self.client.request(Ledger(ledger_index='validated'))
            if validate_xrpl_response_data(ledger_response):
                process_transaction_error(ledger_response)

            # Extract the close time directly in Ripple epoch format
            current_ledger_time = ledger_response.result["ledger"]["close_time"]

            if finish_after_time and cancel_after_time:
                finish_after = set_claim_date(finish_after_time, current_ledger_time)
                cancel_after = set_claim_date(cancel_after_time, current_ledger_time)
                if finish_after >= cancel_after:
                    raise ValueError("FinishAfter must be before CancelAfter.")
                if finish_after <= current_ledger_time:
                    raise ValueError("FinishAfter must be in the future.")
            else:
                # Default to 1 day and 2 days if not provided
                finish_after = current_ledger_time + 86400  # 1 day in seconds
                cancel_after = current_ledger_time + 172800  # 2 days in seconds

            # if finish_after_time and cancel_after_time:
            #     finish_after = set_claim_date(finish_after_time)
            #     logger.info(f"Finish after set to: {finish_after}")
            #
            #     cancel_after = set_claim_date(cancel_after_time)
            #     logger.info(f"Cancel after set to: {cancel_after}")
            # else:
            #     try:
            #         finish_after = set_claim_date(xrpl_config.ESCROW_DEFAULT_FINISH_AFTER_DATE)
            #         print(f"Claim date set to: {finish_after}")
            #     except ValueError as e:
            #         print(f"Error parsing finish_after: {e}")
            #         print(f"Setting finish_after to defaults 1 day")
            #         finish_after = datetime_to_ripple_time(datetime.now() + timedelta(days=1))
            #
            #     try:
            #         cancel_after = set_claim_date(xrpl_config.ESCROW_DEFAULT_CLAIM_AFTER_DATE)
            #         print(f"Claim date set to: {cancel_after}")
            #     except ValueError as e:
            #         print(f"Error parsing cancel_after: {e}")
            #         print(f"Setting cancel_after to defaults 1 day")
            #         cancel_after = datetime_to_ripple_time(datetime.now() + timedelta(days=1))

            condition, fulfillment = generate_escrow_condition_and_fulfillment()

            # sender wallet object
            escrow_creator_seed_wallet = Wallet.from_seed(escrow_creator_seed)

            account_info = self.client.request(AccountInfo(account=escrow_creator_seed_wallet.classic_address))
            sequence = account_info.result["account_data"]["Sequence"]
            fee_response = self.client.request(Fee())
            fee = fee_response.result["drops"]["base_fee"]
            ledger_response = self.client.request(Ledger(ledger_index="current"))
            current_ledger = ledger_response.result["ledger_current_index"]

            # Build escrow create transaction
            create_escrow_txn = create_escrow_transaction_with_finsh_cancel(escrow_creator_seed_wallet.address, Decimal(amount_to_escrow), escrow_account, condition, sequence, str(fee), current_ledger, finish_after, cancel_after)

            # Autofill, sign, then submit transaction and wait for result
            logger.debug(f"Raw transaction before submission: {create_escrow_txn.to_dict()}")
            create_escrow_transaction_response = submit_and_wait(create_escrow_txn, self.client, escrow_creator_seed_wallet)
            logger.debug(f"Response after submission: {create_escrow_transaction_response.to_dict()}")

            # Validate client response. Raise exception on error
            if validate_xrpl_response_data(create_escrow_transaction_response):
                process_transaction_error(create_escrow_transaction_response)

            count_xrp_received(create_escrow_transaction_response.result, escrow_creator_seed_wallet)

            save_create_escrow_response(create_escrow_transaction_response.result, fulfillment)

            # Return result of transaction
            create_escrow_transaction_result = create_escrow_transaction_response.result

            # Parse result and print out the necessary info
            print(create_escrow_transaction_result["tx_json"]["Account"])
            print(create_escrow_transaction_result["tx_json"]["Sequence"])

            print(create_escrow_transaction_result["meta"]["TransactionResult"])
            print(create_escrow_transaction_result["hash"])

            return create_escrow_account_response(create_escrow_transaction_result)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class CancelEscrow(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.cancel_escrow(request)

    def get(self, request, *args, **kwargs):
        return self.cancel_escrow(request)

    def cancel_escrow(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'cancel_escrow'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            escrow_creator_seed = self.request.GET.get('escrow_creator_seed')
            tx_hash = self.request.GET.get('tx_hash')

            if not is_valid_xrpl_seed(escrow_creator_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            # sender wallet object
            sender_wallet = Wallet.from_seed(escrow_creator_seed)

            transaction_id_request = prepare_tx(tx_hash)
            transaction_id_response = self.client.request(transaction_id_request)

            # Validate client response. Raise exception on error
            if validate_xrpl_response_data(transaction_id_response):
                process_transaction_error(transaction_id_response)

            transaction_id_response_result = transaction_id_response.result

            if "Sequence" not in transaction_id_response_result['tx_json']:
                raise XRPLException(error_response("EscrowCreate transaction not found or invalid."))

            escrow_sequence = transaction_id_response_result['tx_json']['Sequence']
            escrow_creator_account = transaction_id_response_result['tx_json']['Account']
            logger.info(f"Escrow Sequence: {escrow_sequence} Escrow creator account: {escrow_creator_account}")

            if "CancelAfter" in transaction_id_response_result['tx_json']:
                cancel_after_time = transaction_id_response_result['tx_json']['CancelAfter']
                # Get the latest ledger sequence
                ledger_index = get_latest_validated_ledger_sequence(self.client)

                # Get the ledger details
                ledger_response = self.client.request(Ledger(ledger_index=ledger_index) )
                if validate_xrpl_response_data(ledger_response):
                    process_transaction_error(ledger_response)

                # Extract the close time directly in Ripple epoch format
                current_ledger_time = ledger_response.result["ledger"]["close_time"]
                if current_ledger_time < cancel_after_time:
                    raise XRPLException(error_response(f"Cannot cancel yet; CancelAfter time ({cancel_after_time}) not reached."))

            # Build escrow cancel transaction
            cancel_escrow_transaction_request = create_cancel_escrow_transaction(sender_wallet.address, escrow_sequence)

            cancel_escrow_transaction_response = submit_and_wait(cancel_escrow_transaction_request, self.client, sender_wallet)

            # Validate client response. Raise exception on error
            if validate_xrpl_response_data(cancel_escrow_transaction_response):
                process_transaction_error(cancel_escrow_transaction_response)

            # Parse response and return result
            return create_escrow_cancel_response(cancel_escrow_transaction_response.result)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class FinishEscrow(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.finish_escrow(request)

    def get(self, request, *args, **kwargs):
        return self.finish_escrow(request)

    def finish_escrow(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'finish_escrow'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            escrow_account = self.request.GET.get('escrow_account')
            escrow_creator_seed = self.request.GET.get('escrow_creator_seed')
            txn_hash = self.request.GET.get('txn_hash')

            if not all([escrow_account, escrow_creator_seed, txn_hash]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(escrow_creator_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not escrow_account and not validate_xrp_wallet(escrow_account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            if not does_account_exist(escrow_account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(escrow_account)))

            escrow_sequence, condition, fulfillment = get_escrow_data_from_db(txn_hash)
            escrow_creator_wallet = Wallet.from_seed(escrow_creator_seed)

            # Verify escrow details
            tx_response = self.client.request(Tx(transaction=txn_hash)).result
            if tx_response['tx_json']["TransactionType"] != "EscrowCreate" or tx_response['tx_json']["Account"] != escrow_creator_wallet.classic_address:
                raise ValueError(f"Transaction {txn_hash} is not an EscrowCreate from {escrow_creator_wallet.classic_address}")
            finish_after = tx_response['meta']['AffectedNodes'][0]['CreatedNode']['NewFields']['FinishAfter']
            if not finish_after:
                raise ValueError(f"Escrow {txn_hash} has no FinishAfter time.")
            original_sequence = tx_response['tx_json']["Sequence"]
            if original_sequence != escrow_sequence:
                raise ValueError(f"Sequence mismatch! DB: {escrow_sequence}, Actual: {original_sequence}")
            ledger_condition = tx_response['meta']['AffectedNodes'][0]['CreatedNode']['NewFields']['Condition']
            if tx_response['meta']['AffectedNodes'][0]['CreatedNode']['NewFields']['Condition'] != condition:
                raise ValueError(f"Condition mismatch! DB: {condition}, Actual: {ledger_condition}")

            # Validate fulfillment matches condition
            fulfillment_bytes = bytes.fromhex(fulfillment[8:])  # Remove prefix
            computed_hash = hashlib.sha256(fulfillment_bytes).hexdigest().upper()
            if computed_hash != condition[8:]:  # Compare without prefix
                raise ValueError(
                    f"Fulfillment does not match condition! Computed: {computed_hash}, Expected: {condition[8:]}")


            # Check current validated ledger time
            current_ledger_response = self.client.request(Ledger(ledger_index="validated")).result
            current_ledger_time = current_ledger_response["ledger"]["close_time"]
            logger.info(f"Current validated ledger time: {current_ledger_time}, FinishAfter: {finish_after}")
            if current_ledger_time < finish_after:
                seconds_to_wait = finish_after - current_ledger_time
                raise ValueError(
                    f"Cannot finish yet. Current time ({current_ledger_time}) < FinishAfter ({finish_after}). Wait {seconds_to_wait} seconds.")

            # Build escrow finish transaction
            finish_escrow_transaction_request = create_finish_escrow_transaction(escrow_creator_wallet.address, escrow_creator_wallet.address, escrow_sequence,condition,fulfillment)
            print(f"FinishEscrow transaction: {finish_escrow_transaction_request.to_dict()}")
            try:
                finish_escrow_transaction_response = submit_and_wait(finish_escrow_transaction_request, self.client, escrow_creator_wallet)
                print(f"Full transaction response: {finish_escrow_transaction_response.result}")
            except Exception as e:
                print(f"submit_and_wait failed with error: {str(e)}")
                logger.error(f"submit_and_wait failed with error: {str(e)}")
                raise  # Re-raise to preserve the original flow

            # Validate client response. Raise exception on error
            if validate_xrpl_response_data(finish_escrow_transaction_response):
                process_transaction_error(finish_escrow_transaction_response)

            print(f"finish_escrow_transaction_response failed with error: {finish_escrow_transaction_response}")

            save_create_escrow_response(finish_escrow_transaction_response.result, fulfillment)

            count_xrp_received(finish_escrow_transaction_response.result, escrow_creator_wallet)

            logger.info(finish_escrow_transaction_response.result["meta"]["TransactionResult"])
            logger.info(finish_escrow_transaction_response.result["hash"])

            return create_finish_escrow_response(finish_escrow_transaction_response.result)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, MultipleObjectsReturned, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class GetEscrowSequenceNumber(View):
    def __init__(self):
        super().__init__()
        self.client = None

    def post(self, request, *args, **kwargs):
        return self.get_escrow_sequence_number(request)

    def get(self, request, *args, **kwargs):
        return self.get_escrow_sequence_number(request)

    def get_escrow_sequence_number(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'get_escrow_sequence_number'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            prev_txn_id = self.request.GET.get('prev_txn_id')
            sequence, tx_hash, ledger_index = get_escrow_sequence(self.client, prev_txn_id)
            if sequence is None and tx_hash:
                return create_escrow_sequence_number_response(None)
            else:
                return create_escrow_sequence_number_response(sequence)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
