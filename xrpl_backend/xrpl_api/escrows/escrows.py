import json
import logging
import time
from decimal import Decimal
import hashlib
from xrpl.models.transactions import EscrowFinish
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
from xrpl.models import Ledger, Fee, AccountInfo, AccountObjects, Tx, AccountObjectType
from xrpl.transaction import submit_and_wait, sign, autofill, submit
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
    is_valid_txn_id_format, does_txn_exist, count_xrp_received, get_ledger_index

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
            data = json.loads(request.body)
            escrow_account = data.get("escrow_account")
            tx_hash = data.get("tx_hash", "")

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
            data = json.loads(request.body)
            prev_txn_id = data.get("prev_txn_id")

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

@method_decorator(csrf_exempt, name="dispatch")
class CreateEscrow(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.create_escrow(request)

    def get(self, request, *args, **kwargs):
        return self.create_escrow(request)

    def create_escrow(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'create_escrow'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            data = json.loads(request.body)
            escrow_receiver_account = data.get("escrow_receiver_account")
            escrow_creator_seed = data.get("escrow_creator_seed")
            amount_to_escrow = data.get("amount_to_escrow")
            finish_after_time = data.get("finish_after_time")
            cancel_after_time = data.get("cancel_after_time")

            if not all([escrow_receiver_account, escrow_creator_seed, amount_to_escrow]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(escrow_creator_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not escrow_receiver_account and not validate_xrp_wallet(escrow_receiver_account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            if not does_account_exist(escrow_receiver_account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(escrow_receiver_account)))

            xrpl_config = apps.get_app_config('xrpl_api')

            if finish_after_time and cancel_after_time:
                finish_after = set_claim_date(finish_after_time)
                logger.info(f"Finish after set to: {finish_after}")

                cancel_after = set_claim_date(cancel_after_time)
                logger.info(f"Cancel after set to: {cancel_after}")
            else:
                try:
                    finish_after = set_claim_date(xrpl_config.ESCROW_DEFAULT_FINISH_AFTER_DATE)
                    print(f"Claim date set to: {finish_after}")
                except ValueError as e:
                    print(f"Error parsing finish_after: {e}")
                    print(f"Setting finish_after to defaults 1 day")
                    finish_after = datetime_to_ripple_time(datetime.now() + timedelta(days=1))

                try:
                    cancel_after = set_claim_date(xrpl_config.ESCROW_DEFAULT_CLAIM_AFTER_DATE)
                    print(f"Claim date set to: {cancel_after}")
                except ValueError as e:
                    print(f"Error parsing cancel_after: {e}")
                    print(f"Setting cancel_after to defaults 1 day")
                    cancel_after = datetime_to_ripple_time(datetime.now() + timedelta(days=1))

            # condition, fulfillment = generate_escrow_condition_and_fulfillment()
            condition='A02580203781B63F53E0C5F8C99BB20136277B4FEE1DB228B9A001E44003DD58561FC7ED810120'
            fulfillment='A02280205AD4FBF109BEDD242EB2E16C81C6A4D0EE4DD549CCBC47A4D230B39AD6A64FDB'
            print(f"\nGenerated condition: {condition} fulfillment: {fulfillment}")

            # sender wallet object
            escrow_creator_seed_wallet = Wallet.from_seed(escrow_creator_seed)

            account_info = self.client.request(AccountInfo(account=escrow_creator_seed_wallet.classic_address))
            # sequence = account_info.result["account_data"]["Sequence"]
            # fee_response = self.client.request(Fee())
            # fee = fee_response.result["drops"]["base_fee"]
            sequence=""
            fee=""
            ledger_response = self.client.request(Ledger(ledger_index="current"))
            current_ledger = ledger_response.result["ledger_current_index"]

            # Build escrow create transaction
            create_escrow_txn = create_escrow_transaction_with_finsh_cancel(escrow_creator_seed_wallet.address, Decimal(amount_to_escrow), escrow_receiver_account, condition, sequence, str(fee), current_ledger, finish_after, cancel_after)

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
            # print(create_escrow_transaction_result["tx_json"]["Account"])
            print(create_escrow_transaction_result["tx_json"]["Sequence"])

            # print(create_escrow_transaction_result["meta"]["TransactionResult"])
            print(create_escrow_transaction_result["hash"])

            print(f"\nGenerated condition: {condition} fulfillment: {fulfillment}")
            db_row = get_escrow_data_from_db(create_escrow_transaction_result["hash"])
            print(f"db row: {db_row}")
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
            data = json.loads(request.body)
            escrow_creator_seed = data.get("escrow_creator_seed")
            tx_hash = data.get("tx_hash")

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
            data = json.loads(request.body)
            escrow_receiver_account = data.get("escrow_receiver_account")
            escrow_receiver_seed = data.get("escrow_receiver_seed")
            escrow_creator_seed = data.get("escrow_creator_seed")
            txn_hash = data.get("txn_hash")

            if not all([escrow_receiver_account, escrow_creator_seed, txn_hash, escrow_receiver_seed]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(escrow_creator_seed) or not is_valid_xrpl_seed(escrow_receiver_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))
            if not validate_xrp_wallet(escrow_receiver_account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))
            if not does_account_exist(escrow_receiver_account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(escrow_receiver_account)))

            escrow_sequence, condition1, fulfillment1 = get_escrow_data_from_db(txn_hash)
            condition = 'A02580203781B63F53E0C5F8C99BB20136277B4FEE1DB228B9A001E44003DD58561FC7ED810120'
            fulfillment = 'A02280205AD4FBF109BEDD242EB2E16C81C6A4D0EE4DD549CCBC47A4D230B39AD6A64FDB'

            escrow_creator_wallet = Wallet.from_seed(escrow_creator_seed)
            logger.info(f"Creator address: {escrow_creator_wallet.classic_address}")
            escrow_receiver_wallet = Wallet.from_seed(escrow_receiver_seed)
            logger.info(f"Reciever address: {escrow_receiver_wallet.classic_address}")

            # Verify escrow details
            tx_response = self.client.request(Tx(transaction=txn_hash)).result
            if tx_response['tx_json']["TransactionType"] != "EscrowCreate" or tx_response['tx_json']["Account"] != escrow_creator_wallet.classic_address:
                raise ValueError(f"Transaction {txn_hash} is not an EscrowCreate from {escrow_creator_wallet.classic_address}")
            finish_after = tx_response['tx_json'].get("FinishAfter")
            if not finish_after:
                raise ValueError(f"Escrow {txn_hash} has no FinishAfter time.")
            original_sequence = tx_response['tx_json']["Sequence"]
            if original_sequence != escrow_sequence:
                raise ValueError(f"Sequence mismatch! DB: {escrow_sequence}, Actual: {original_sequence}")
            ledger_condition = tx_response['tx_json']["Condition"]
            if ledger_condition != condition:
                raise ValueError(f"Condition mismatch! DB: {condition}, Actual: {ledger_condition}")

            escrow_sequence = 5065862

            # Validate fulfillment matches condition
            fulfillment_preimage = bytes.fromhex(fulfillment[8:])  # Raw preimage without 'A0228020'
            computed_hash = hashlib.sha256(fulfillment_preimage).hexdigest().upper()
            condition_hash = condition[8:-6]  # Hash without 'A0258020' and '810120'
            if computed_hash != condition_hash:
                raise ValueError(f"Fulfillment does not match condition! Computed: {computed_hash}, Expected: {condition_hash}")

            # Check current validated ledger time
            current_ledger_response = self.client.request(Ledger(ledger_index="validated"))
            current_ledger_time = current_ledger_response.result["ledger"]["close_time"]
            logger.info(f"Current validated ledger time: {current_ledger_time}, FinishAfter: {finish_after}")
            if current_ledger_time < finish_after:
                seconds_to_wait = finish_after - current_ledger_time
                raise ValueError(f"Cannot finish yet. Current time ({current_ledger_time}) < FinishAfter ({finish_after}). Wait {seconds_to_wait} seconds.")

            # Verify escrow exists
            escrow_check = self.client.request(AccountObjects(account=escrow_creator_wallet.classic_address, type=AccountObjectType.ESCROW)).result
            escrow_found = False
            for obj in escrow_check["account_objects"]:
                if obj["PreviousTxnID"] == txn_hash:
                    escrow_found = True
                    logger.info(f"Escrow found: {obj}")
                    break
            if not escrow_found:
                raise ValueError(f"Escrow for txn {txn_hash} not found in account objects!")

            # Check submitter flags
            account_info = self.client.request(AccountInfo(account=escrow_creator_wallet.classic_address)).result
            logger.info(f"Submitter account flags: {account_info['account_data']['Flags']}")

            # Fetch the validated ledger index
            ledger_response = self.client.request(Ledger(ledger_index="validated"))
            current_ledger = ledger_response.result["ledger_index"]
            last_ledger_sequence = current_ledger + 500  # Try +1000 if needed
            logger.info(
                f"Step 1 - Fetched ledger at {time.time():.3f}: Current validated ledger index: {current_ledger}, Calculated LastLedgerSequence: {last_ledger_sequence}")

            # Build transaction
            finish_escrow_txn = EscrowFinish(
                account=escrow_creator_wallet.address,
                owner=escrow_receiver_wallet.address,
                offer_sequence=escrow_sequence,
                condition=condition,
                fulfillment=fulfillment,
                last_ledger_sequence=last_ledger_sequence,
            )
            logger.info(f"Step 2 - Built transaction at {time.time():.3f}: {finish_escrow_txn.to_dict()}")

            # Autofill and sign
            autofilled_tx = autofill(finish_escrow_txn, self.client)
            logger.info(
                f"Step 3 - Autofilled transaction at {time.time():.3f}: LastLedgerSequence: {autofilled_tx.last_ledger_sequence}")

            signed_tx = sign(autofilled_tx, escrow_creator_wallet)
            logger.info(
                f"Step 4 - Signed transaction at {time.time():.3f}: LastLedgerSequence: {signed_tx.last_ledger_sequence}")

            # Submit without waiting
            logger.info(f"Step 5 - Submitting transaction at {time.time():.3f}")
            try:
                # Submit the signed transaction
                response = submit(signed_tx, self.client)
                tx_hash = response.result.get("hash") or signed_tx.get_hash()
                logger.info(
                    f"Step 6 - Transaction submitted at {time.time():.3f}, hash: {tx_hash}, submit response: {response.result}")

                # Poll for validation with extended window
                max_attempts = 30  # 60 seconds total
                attempt_interval = 2  # Seconds between attempts
                for attempt in range(max_attempts):
                    try:
                        tx_response = self.client.request(Tx(transaction=tx_hash)).result
                        logger.debug(f"Attempt {attempt + 1}/{max_attempts} - Tx status: {tx_response}")
                        if tx_response.get("validated", False):
                            logger.info(f"Step 7 - Transaction validated at {time.time():.3f}: {tx_response}")
                            save_create_escrow_response(tx_response, fulfillment)
                            count_xrp_received(tx_response, escrow_creator_wallet.address)
                            return create_finish_escrow_response(tx_response)
                        elif "meta" in tx_response and "TransactionResult" in tx_response["meta"]:
                            # If it failed, stop polling and report the result
                            result = tx_response["meta"]["TransactionResult"]
                            logger.error(f"Transaction failed with result: {result}, full response: {tx_response}")
                            raise Exception(f"Transaction failed: {result}")
                    except Exception as e:
                        logger.debug(f"Attempt {attempt + 1}/{max_attempts} - Tx check failed: {e}")
                    time.sleep(attempt_interval)
                else:
                    logger.error(f"Transaction {tx_hash} not validated after {max_attempts * attempt_interval} seconds")
                    # Final check before giving up
                    try:
                        final_response = self.client.request(Tx(transaction=tx_hash)).result
                        logger.error(f"Final transaction status: {final_response}")
                    except Exception as e:
                        logger.error(f"Final status check failed: {e}")
                    raise Exception(
                        f"Transaction {tx_hash} failed to validate within {max_attempts * attempt_interval} seconds")
            except Exception as e:
                logger.error(f"Submission or polling failed at {time.time():.3f} with error: {str(e)}")
                tx_hash = signed_tx.get_hash() if "tx_hash" not in locals() else tx_hash
                logger.info(f"Submitted tx hash: {tx_hash}")
                try:
                    tx_result = self.client.request(Tx(transaction=tx_hash)).result
                    logger.error(f"Ledger tx result: {tx_result}")
                except Exception as tx_e:
                    logger.error(f"Failed to fetch tx result: {tx_e}")
                raise

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, MultipleObjectsReturned, ValueError) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
