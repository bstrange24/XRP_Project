import datetime
import json
import logging
import math
import time
from datetime import datetime
from decimal import Decimal

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.clients import XRPLRequestFailureException
from xrpl.core.addresscodec import XRPLAddressCodecException
from xrpl.models import Ledger, Fee
from xrpl.transaction import submit_and_wait, sign
from xrpl.utils import datetime_to_ripple_time
from xrpl.utils import drops_to_xrp, ripple_time_to_datetime
from xrpl.wallet import Wallet

from .db_operations.escrow_db_operations import save_create_escrow_response
from .escrows_util import create_escrow_account_transaction, \
    create_cancel_escrow_transaction, get_escrow_account_response, \
    get_escrow_tx_id_account_response, generate_escrow_condition_and_fulfillment, create_escrow_account_response, \
    set_claim_date, create_escrow_sequence_number_response, \
    get_escrow_sequence, create_escrow_cancel_response, validate_fulfillment, create_escrow_transaction_time_based_only, \
    create_escrow_transaction_condition_only, format_ripple_time, create_finish_escrow_time_based_response, create_finish_escrow_transaction, log_postman_finish_escrow_request, create_finish_escrow_time_based_transaction
from ..accounts.account_utils import prepare_account_data, prepare_account_tx, prepare_account_signers
from ..constants.constants import ENTERING_FUNCTION_LOG, LEAVING_FUNCTION_LOG, INVALID_WALLET_IN_REQUEST, \
    ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, SENDER_SEED_IS_INVALID, MISSING_REQUEST_PARAMETERS, INVALID_TX_ID_IN_REQUEST, INVALID_TRANSACTION_HASH
from ..errors.error_handling import process_transaction_error, handle_error_new, error_response, \
    process_unexpected_error
from ..transactions.transactions_util import prepare_tx
from ..utilities.base_xrpl_view import BaseXRPLView
from ..utilities.utilities import total_execution_time_in_millis, validate_xrp_wallet, is_valid_xrpl_seed, validate_xrpl_response_data, \
    is_valid_txn_id_format, does_txn_exist, count_xrp_received, is_valid_ledger_transaction_hash, convert_drops_to_xrp, validate_response, get_ledger_index, get_base_fee, get_ledger_current_index, get_ledger_index_and_close_time

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class GetEscrowAccountInfo(BaseXRPLView):
    def __init__(self):
        super().__init__()

    def post(self, request):
        return self.get_account_escrow_info(request)

    def get(self, request):
        return self.get_account_escrow_info(request)

    def get_account_escrow_info(self, request):
        start_time = time.time()
        function_name = 'get_account_escrow_info'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            data = json.loads(request.body)
            escrow_account = data.get("escrow_account")
            tx_hash = data.get("tx_hash", "")

            # Check if both parameters are missing
            if not escrow_account and not tx_hash:
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            # Determine query type
            query_by_account = bool(escrow_account)  # Prioritize account if both provided
            query_by_txn = tx_hash and not query_by_account

            # Validate account if provided
            if query_by_account:
                if not validate_xrp_wallet(escrow_account):
                    raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))
                if not does_account_exist(escrow_account, self.client):
                    raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(escrow_account)))

            # Validate transaction ID if querying by tx_hash
            if query_by_txn:
                if not is_valid_txn_id_format(tx_hash) or not does_txn_exist(tx_hash, self.client):
                    raise XRPLException(error_response(INVALID_TX_ID_IN_REQUEST))

            if query_by_account:
                logger.info(f"Getting escrow based on account: {escrow_account}")

                # Build and make request
                escrow_account_request = create_escrow_account_transaction(escrow_account)
                escrow_account_response = self.client.request(escrow_account_request)
                validate_response(escrow_account_response, "Failed to fetch account escrows")

                # Return account escrows
                escrows = escrow_account_response.result["account_objects"]
                all_escrows = {"sent": [], "received": []}

                # Loop through result and parse account escrows
                for escrow in escrows:
                    escrow_data = {
                        "escrow_id": escrow["index"],
                        "sender": escrow["Account"],
                        "receiver": escrow["Destination"],
                        "amount": str(drops_to_xrp(str(escrow["Amount"]))) if isinstance(escrow["Amount"], str) else str(escrow["Amount"])
                    }

                    # Fetch sequence and transaction details
                    sequence, tx_hash, ledger_index = get_escrow_sequence(self.client, escrow["PreviousTxnID"])
                    escrow_data["Sequence"] = sequence
                    escrow_data["prex_txn_id"] = escrow.get("PreviousTxnID", "")

                    # Add optional fields
                    if "FinishAfter" in escrow:
                        escrow_data["redeem_date"] = str(ripple_time_to_datetime(escrow["FinishAfter"]))
                    if "CancelAfter" in escrow:
                        escrow_data["expiry_date"] = str(ripple_time_to_datetime(escrow["CancelAfter"]))
                    if "Condition" in escrow:
                        escrow_data["condition"] = escrow["Condition"]

                    # Categorize escrow
                    if escrow_data["sender"] == escrow_account:
                        all_escrows["sent"].append(escrow_data)
                    else:
                        all_escrows["received"].append(escrow_data)

                return get_escrow_account_response(all_escrows)
            else:
                logger.info(f"Getting escrow based on txn id: {tx_hash}")
                # Build and send query for PreviousTxnID
                transaction_id_request = prepare_tx(tx_hash)
                transaction_id_response = self.client.request(transaction_id_request)
                validate_response(transaction_id_response, "Failed to fetch transaction")

                tx_data = transaction_id_response.result
                if "Sequence" not in transaction_id_response.result['tx_json']:
                    raise XRPLException(error_response("EscrowCreate transaction not found or invalid."))

                # Log sequence or ticket sequence
                logger.debug(f"Escrow sequence: {tx_data['tx_json'].get('Sequence', 'N/A')}")
                if "TicketSequence" in tx_data['tx_json']:
                    logger.debug(f"Escrow ticket sequence: {tx_data['tx_json']['TicketSequence']}")

                return get_escrow_tx_id_account_response(tx_data)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class GetEscrowSequenceNumber(BaseXRPLView):
    def __init__(self):
        super().__init__()

    def post(self, request):
        return self.get_escrow_sequence_number(request)

    def get(self, request):
        return self.get_escrow_sequence_number(request)

    def get_escrow_sequence_number(self, request):
        start_time = time.time()
        function_name = 'get_escrow_sequence_number'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

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
class CreateEscrowTimeBased(BaseXRPLView):
    def __init__(self):
        super().__init__()

    def post(self, request):
        return self.create_escrow_time_based(request)

    def get(self, request):
        return self.create_escrow_time_based(request)

    def create_escrow_time_based(self, request):
        start_time = time.time()
        function_name = 'create_escrow'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            data = json.loads(request.body)
            escrow_receiver_account = data.get("escrow_receiver_account")
            escrow_creator_seed = data.get("escrow_creator_seed")
            amount_to_escrow = data.get("amount_to_escrow")
            finish_after_time = data.get("finish_after_time")
            cancel_after_time = data.get("cancel_after_time")
            create_escrow_transaction_response = None

            if not all([escrow_receiver_account, escrow_creator_seed, amount_to_escrow, finish_after_time, cancel_after_time]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(escrow_creator_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            escrow_creator_seed_wallet = Wallet.from_seed(escrow_creator_seed)
            logger.info(f"Escrow receiver account: {escrow_receiver_account} Escrow creator wallet: {escrow_creator_seed_wallet.classic_address} Amount to Escrow: {amount_to_escrow}")
            logger.info(f"Finish After Time: {finish_after_time} Cancel After Time: {cancel_after_time}")

            if not does_account_exist(escrow_creator_seed_wallet.classic_address, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(escrow_creator_seed_wallet.classic_address)))
            if not validate_xrp_wallet(escrow_receiver_account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))
            if not does_account_exist(escrow_receiver_account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(escrow_receiver_account)))

            try:
                finish_after = set_claim_date(finish_after_time)
                logger.warning(f"Claim date set to: {finish_after}")
            except ValueError as e:
                logger.error(f"Error parsing finish_after: {e}")
                process_unexpected_error(e)

            try:
                cancel_after = set_claim_date(cancel_after_time)
                logger.warning(f"Claim date set to: {cancel_after}")
            except ValueError as e:
                logger.error(f"Error parsing cancel_after: {e}")
                process_unexpected_error(e)

            current_ripple_time = datetime_to_ripple_time(datetime.now())
            logger.debug(f"Current Ripple time: {current_ripple_time}, Finish: {finish_after}, Cancel: {cancel_after}")

            sequence = self.client.request(prepare_account_data(escrow_creator_seed_wallet.classic_address, True)).result["account_data"]["Sequence"]
            fee = get_base_fee(self.client)
            current_ledger = get_ledger_current_index(self.client, "current")

            # Build escrow create transaction
            create_escrow_txn = create_escrow_transaction_time_based_only(escrow_creator_seed_wallet.classic_address, Decimal(amount_to_escrow),
                                                                          escrow_receiver_account, sequence, str(fee), current_ledger, finish_after, cancel_after)

            # Autofill, sign, then submit transaction and wait for result
            logger.debug(f"Raw create_escrow_txn before submission: {create_escrow_txn.to_dict()}")
            try:
                logger.info("Signing the transaction")
                signed_tx = sign(create_escrow_txn, escrow_creator_seed_wallet)
                logger.debug(f"Signed transaction: {signed_tx.to_dict()}")

                logger.info("signing and submitting the transaction, awaiting a response")
                create_escrow_transaction_response = submit_and_wait(signed_tx, self.client, escrow_creator_seed_wallet)
                logger.debug(f"Response after submission: {create_escrow_transaction_response.to_dict()}")
                validate_response(create_escrow_transaction_response, "Escrow creation failed")
            except XRPLException as e:
                print(f"Error: {e}")
                process_unexpected_error(e)

            count_xrp_received(create_escrow_transaction_response.result, escrow_creator_seed_wallet)
            save_create_escrow_response(create_escrow_transaction_response.result, "")
            return create_escrow_account_response(create_escrow_transaction_response.result)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class FinishEscrowTimeBased(BaseXRPLView):
    def __init__(self):
        super().__init__()

    def post(self, request):
        return self.finish_escrow_time_based(request)

    def get(self, request):
        return self.finish_escrow_time_based(request)

    def finish_escrow_time_based(self, request):
        start_time = time.time()
        function_name = 'finish_escrow'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            self._initialize_client()
            data = json.loads(request.body)
            escrow_creator_account_seed = data.get("escrow_creator_account_seed")
            escrow_receiver_account = data.get("escrow_receiver_account")
            escrow_receiver_account_seed = data.get("escrow_receiver_account_seed")
            offer_sequence = data.get("offer_sequence")
            escrow_hash = data.get("prev_txn_id")

            # Validate wallets and accounts
            if not all([escrow_creator_account_seed, offer_sequence, escrow_receiver_account, escrow_hash]):
                raise ValueError(MISSING_REQUEST_PARAMETERS)
            if not validate_xrp_wallet(escrow_receiver_account):
                raise ValueError(INVALID_WALLET_IN_REQUEST)
            if not does_account_exist(escrow_receiver_account, self.client):
                raise ValueError(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(escrow_receiver_account))
            if not is_valid_ledger_transaction_hash(escrow_hash, self.client):
                raise ValueError(INVALID_TRANSACTION_HASH)
            if not is_valid_xrpl_seed(escrow_creator_account_seed):
                raise ValueError(SENDER_SEED_IS_INVALID)

            # Create wallets
            creator_wallet = Wallet.from_seed(escrow_creator_account_seed)
            receiver_wallet = Wallet.from_seed(escrow_receiver_account_seed) if escrow_receiver_account_seed else None
            submit_wallet = receiver_wallet if receiver_wallet else creator_wallet
            submit_account = escrow_receiver_account if receiver_wallet else creator_wallet.address
            logger.info(f"Creator address: {creator_wallet.address}")
            logger.info(f"Receiver address: {escrow_receiver_account}")
            logger.info(f"Submitting as: {submit_account}")

            # Get account sequence
            account_sequence = self.client.request(prepare_account_data(submit_account, False)).result["account_data"]["Sequence"]
            logger.info(f"Submitting account sequence: {account_sequence}")

            # Verify escrow exists
            account_objects = self.client.request(create_escrow_account_transaction(creator_wallet.address)).result.get("account_objects", [])
            escrow_exist = False
            account_object = None
            for obj in account_objects:
                if obj["LedgerEntryType"] == "Escrow" and obj["PreviousTxnID"] == escrow_hash:
                    escrow_exist = True
                    account_object = obj
                    break

            if not escrow_exist:
                raise ValueError(f"Escrow with hash {escrow_hash} not found")

            finish_after_time = account_object["FinishAfter"]
            cancel_after_time = account_object.get("CancelAfter")
            logger.info(f"Escrow object: {account_object}")
            logger.info(f"Finish after: {format_ripple_time(ripple_time_to_datetime(finish_after_time))}")
            if cancel_after_time:
                logger.info(f"Cancel after: {format_ripple_time(ripple_time_to_datetime(cancel_after_time))}")

            # Validate EscrowCreate transaction
            tx_result = self.client.request(prepare_tx(escrow_hash)).result
            logger.info(f"EscrowCreate transaction: {tx_result}")
            if tx_result["tx_json"]["TransactionType"] != "EscrowCreate" or tx_result["tx_json"]["Sequence"] != int(offer_sequence):
                raise ValueError(f"Escrow hash {escrow_hash} does not match sequence {offer_sequence}")
            if "Condition" in tx_result["tx_json"]:
                raise ValueError("Escrow has a Condition, which is not supported")

            # Check recent transactions
            try:
                account_tx_response = self.client.request(prepare_account_tx(creator_wallet.address))
                if account_tx_response.result.get("status") == "error":
                    logger.warning(f"AccountTx error: {account_tx_response.result.get('error_message', 'Unknown error')}")
                else:
                    transactions = account_tx_response.result.get("transactions", [])
                    for tx in transactions:
                        if (tx["tx_json"].get("TransactionType") in ["EscrowFinish", "EscrowCancel"] and
                                tx["tx_json"].get("OfferSequence") == int(offer_sequence)):
                            raise ValueError(f"Escrow already finished or canceled in transaction {tx['tx_json']['hash']}")
            except Exception as e:
                logger.warning(f"Failed to check recent transactions: {str(e)}. Proceeding with caution.")

            # Fetch ledger time
            current_ledger_index, close_time_ripple = get_ledger_index_and_close_time(self.client, "validated")
            logger.info(f"Current ledger time (ripple): {close_time_ripple}")
            logger.info(f"Current ledger time (human): {format_ripple_time(ripple_time_to_datetime(close_time_ripple))}")
            logger.info(f"Current ledger index: {current_ledger_index}")
            logger.info(f"FinishAfter time (ripple): {finish_after_time}")
            logger.info(f"FinishAfter time (human): {format_ripple_time(ripple_time_to_datetime(finish_after_time))}")
            logger.info(f"Time difference (seconds): {close_time_ripple - finish_after_time}")

            # Timing check for FinishAfter
            if finish_after_time >= close_time_ripple - 60:
                raise ValueError(
                    f"Escrow cannot be finished yet. FinishAfter: {finish_after_time} "
                    f"({format_ripple_time(ripple_time_to_datetime(finish_after_time))}), "
                    f"Ledger time: {close_time_ripple} "
                    f"({format_ripple_time(ripple_time_to_datetime(close_time_ripple))}), "
                    f"Time difference: {close_time_ripple - finish_after_time} seconds"
                )

            # Warn about CancelAfter but proceed
            if cancel_after_time and close_time_ripple > cancel_after_time:
                logger.warning(f"Ledger time {close_time_ripple} is past CancelAfter {cancel_after_time} ({format_ripple_time(ripple_time_to_datetime(cancel_after_time))}). Escrow object exists, attempting to finish.")

            fee = get_base_fee(self.client)

            # Build EscrowFinish transaction
            finish_tx = create_finish_escrow_time_based_transaction(submit_account, creator_wallet.address, int(offer_sequence), account_sequence, str(fee), current_ledger_index)
            logger.info(f"EscrowFinish transaction (pre-sign): {finish_tx.to_dict()}")

            # Sign and submit
            signed_tx = sign(finish_tx, submit_wallet)
            logger.debug(f"Signed transaction: {signed_tx.to_dict()}")
            submit_start = time.time()
            finish_escrow_transaction_response = submit_and_wait(signed_tx, self.client)
            logger.info(f"Submission took {time.time() - submit_start} seconds")
            logger.debug(f"Full transaction response: {finish_escrow_transaction_response.result}")
            validate_response(finish_escrow_transaction_response, "Escrow finish failed")
            logger.debug(f"Ledger index at submission: {get_ledger_current_index(self.client, "current")}")

            return create_finish_escrow_time_based_response(finish_escrow_transaction_response.result)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class CreateEscrowConditionBased(BaseXRPLView):
    def __init__(self):
        super().__init__()

    def post(self, request):
        return self.create_escrow_condition_based(request)

    def get(self, request):
        return self.create_escrow_condition_based(request)

    def create_escrow_condition_based(self, request):
        start_time = time.time()
        function_name = 'create_escrow_condition_based'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            data = json.loads(request.body)
            escrow_receiver_account = data.get("escrow_receiver_account")
            escrow_receiver_account_seed = data.get("escrow_receiver_account_seed")
            escrow_creator_seed = data.get("escrow_creator_seed")
            amount_to_escrow = data.get("amount_to_escrow")
            finish_after_time = data.get("finish_after_time")
            cancel_after_time = data.get("cancel_after_time")
            create_escrow_transaction_response = None

            if not all([escrow_receiver_account, escrow_creator_seed, amount_to_escrow]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            logger.debug(f"Escrow receiver account: {escrow_receiver_account} Escrow Creator Seed: {escrow_creator_seed} Amount to Escrow: {amount_to_escrow}")

            if not is_valid_xrpl_seed(escrow_creator_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            escrow_creator_seed_wallet = Wallet.from_seed(escrow_creator_seed)
            if not does_account_exist(escrow_creator_seed_wallet.classic_address, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(escrow_creator_seed_wallet.classic_address)))

            if not validate_xrp_wallet(escrow_receiver_account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            if not does_account_exist(escrow_receiver_account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(escrow_receiver_account)))

            finish_after = set_claim_date(finish_after_time)
            logger.info(f"Finish after set to: {finish_after}")
            cancel_after = set_claim_date(cancel_after_time)
            logger.info(f"Cancel after set to: {cancel_after}")
            current_ripple_time = datetime_to_ripple_time(datetime.now())
            logger.debug(f"Current Ripple time: {current_ripple_time}, Finish: {finish_after}")

            condition, fulfillment = generate_escrow_condition_and_fulfillment()
            # Validate fulfillment matches condition
            if not validate_fulfillment(condition, fulfillment):
                raise ValueError(f"Fulfillment does not match condition!")

            sequence = self.client.request(prepare_account_data(escrow_creator_seed_wallet.classic_address, False)).result["account_data"]["Sequence"]

            fee = self.client.request(Fee()).result["drops"]["base_fee"]
            logger.info(f"Base fee: {fee}")
            current_ledger = self.client.request(Ledger(ledger_index="current")).result["ledger_current_index"]

            # Build escrow create transaction
            create_escrow_txn = create_escrow_transaction_condition_only(escrow_creator_seed_wallet.classic_address, Decimal(amount_to_escrow),
                                                                         escrow_receiver_account, condition, sequence, str(fee), current_ledger, finish_after, cancel_after)

            # Autofill, sign, then submit transaction and wait for result
            logger.debug(f"Raw create_escrow_txn before submission: {create_escrow_txn.to_dict()}")
            try:
                logger.info("Signing the transaction")
                signed_tx = sign(create_escrow_txn, escrow_creator_seed_wallet)
                logger.debug(f"Signed transaction: {signed_tx.to_dict()}")

                logger.info("signing and submitting the transaction, awaiting a response")
                create_escrow_transaction_response = submit_and_wait(signed_tx, self.client, escrow_creator_seed_wallet)
                logger.debug(f"Response after submission: {create_escrow_transaction_response.to_dict()}")
            except XRPLException as e:
                print(f"Error: {e}")
                process_unexpected_error(e)

            # Validate client response. Raise exception on error
            if validate_xrpl_response_data(create_escrow_transaction_response):
                process_transaction_error(create_escrow_transaction_response)

            count_xrp_received(create_escrow_transaction_response.result, escrow_creator_seed_wallet)
            save_create_escrow_response(create_escrow_transaction_response.result, fulfillment)
            create_escrow_transaction_response.result['condition'] = condition
            create_escrow_transaction_response.result['fulfillment'] = fulfillment
            create_escrow_transaction_response.result['Sequence'] = create_escrow_transaction_response.result['tx_json']['Sequence']
            create_escrow_transaction_response.result['prex_txn_id'] = create_escrow_transaction_response.result['hash']

            log_postman_finish_escrow_request(create_escrow_transaction_response.result, escrow_creator_seed, escrow_receiver_account, escrow_receiver_account_seed,
                                              condition, fulfillment)

            return create_escrow_account_response(create_escrow_transaction_response.result)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class FinishEscrowConditionBased(BaseXRPLView):
    def __init__(self):
        super().__init__()

    def post(self, request):
        return self.finish_escrow_condition_based(request)

    def get(self, request):
        return self.finish_escrow_condition_based(request)

    def finish_escrow_condition_based(self, request):
        start_time = time.time()
        function_name = 'finish_escrow_condition_based'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            self._initialize_client()
            data = json.loads(request.body)
            escrow_creator_account_seed = data.get("escrow_creator_account_seed")
            escrow_receiver_account = data.get("escrow_receiver_account")
            escrow_receiver_account_seed = data.get("escrow_receiver_account_seed")
            condition = data.get("condition")
            fulfillment = data.get("fulfillment")
            offer_sequence = data.get("offer_sequence")
            escrow_hash = data.get("prev_txn_id")

            # Validate wallets and accounts
            if not all([escrow_creator_account_seed, offer_sequence, escrow_receiver_account, escrow_hash]):
                raise ValueError(MISSING_REQUEST_PARAMETERS)
            if not validate_xrp_wallet(escrow_receiver_account):
                raise ValueError(INVALID_WALLET_IN_REQUEST)
            if not does_account_exist(escrow_receiver_account, self.client):
                raise ValueError(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(escrow_receiver_account))
            if not is_valid_ledger_transaction_hash(escrow_hash, self.client):
                raise ValueError(INVALID_TRANSACTION_HASH)
            if not is_valid_xrpl_seed(escrow_creator_account_seed):
                raise ValueError(SENDER_SEED_IS_INVALID)

            # Create wallets
            creator_wallet = Wallet.from_seed(escrow_creator_account_seed)
            receiver_wallet = Wallet.from_seed(escrow_receiver_account_seed) if escrow_receiver_account_seed else None
            submit_wallet = receiver_wallet if receiver_wallet else creator_wallet
            submit_account = escrow_receiver_account if receiver_wallet else creator_wallet.address
            logger.info(f"Creator address: {creator_wallet.address}")
            logger.info(f"Receiver address: {escrow_receiver_account}")
            logger.info(f"Submitting as: {submit_account}")

            # Validate fulfillment matches condition
            if not validate_fulfillment(condition, fulfillment):
                raise ValueError(f"Fulfillment does not match condition!")

            # Get account sequence
            account_sequence = self.client.request(prepare_account_data(submit_account, False)).result["account_data"]["Sequence"]
            logger.info(f"Submitting account sequence: {account_sequence}")

            # Verify escrow exists
            account_objects = self.client.request(create_escrow_account_transaction(creator_wallet.address)).result.get("account_objects", [])
            escrow_exist = False
            account_object = None
            for obj in account_objects:
                if obj["LedgerEntryType"] == "Escrow" and obj["PreviousTxnID"] == escrow_hash:
                    escrow_exist = True
                    account_object = obj
                    break

            if not escrow_exist:
                raise ValueError(f"Escrow with hash {escrow_hash} not found")

            finish_after_time = account_object["FinishAfter"]
            cancel_after_time = account_object.get("CancelAfter")
            logger.info(f"Escrow object: {account_object}")
            logger.info(f"Finish after: {format_ripple_time(ripple_time_to_datetime(finish_after_time))}")
            if cancel_after_time:
                logger.info(f"Cancel after: {format_ripple_time(ripple_time_to_datetime(cancel_after_time))}")

            # Validate EscrowCreate transaction
            tx_result = self.client.request(prepare_tx(escrow_hash)).result
            logger.info(f"EscrowCreate transaction: {tx_result}")
            if tx_result["tx_json"]["TransactionType"] != "EscrowCreate" or tx_result["tx_json"]["Sequence"] != int(offer_sequence):
                raise ValueError(f"Escrow hash {escrow_hash} does not match sequence {offer_sequence}")

            # Check recent transactions
            try:
                account_tx_response = self.client.request(prepare_account_tx(creator_wallet.address))
                if account_tx_response.result.get("status") == "error":
                    logger.warning(f"AccountTx error: {account_tx_response.result.get('error_message', 'Unknown error')}")
                else:
                    transactions = account_tx_response.result.get("transactions", [])
                    for tx in transactions:
                        if (tx["tx_json"].get("TransactionType") in ["EscrowFinish", "EscrowCancel"] and
                                tx["tx_json"].get("OfferSequence") == int(offer_sequence)):
                            raise ValueError(f"Escrow already finished or canceled in transaction {tx['tx_json']['hash']}")
            except Exception as e:
                logger.warning(f"Failed to check recent transactions: {str(e)}. Proceeding with caution.")

            # Extract signer list and count signers
            account_signers_response = self.client.request(prepare_account_signers(creator_wallet.address))
            signer_list = next((obj for obj in account_signers_response.result["account_objects"] if obj["LedgerEntryType"] == "SignerList"), None)
            num_signers = len(signer_list["SignerEntries"]) if signer_list else 0
            logger.info(f"Number of signers: {num_signers}")

            response = self.client.request(Fee())
            fee = response.result["drops"]["base_fee"]
            logger.info(f"Base fee: {fee}")
            reference_fee = response.result["drops"]["open_ledger_fee"]
            logger.info(f"Reference fee: {reference_fee}")

            fulfillment_bytes = bytes.fromhex(fulfillment)
            fulfillment_size = len(fulfillment_bytes)  # e.g., 32 bytes
            fulfillment_fee = int(reference_fee) * (num_signers + 33 + (fulfillment_size / 16))
            logger.info(f"Fulfillment fee: {fulfillment_fee}")
            fee = fee + str(fulfillment_fee)
            fee = str(math.ceil(float(fee)))
            logger.info(f"Total fees in drops: {fee} Total fees in XRP: {convert_drops_to_xrp(str(math.ceil(float(fee))))}")

            # Fetch ledger time
            current_ledger_index, close_time_ripple = get_ledger_index_and_close_time(self.client, "validated")
            logger.info(f"Current ledger time (ripple): {close_time_ripple}")
            logger.info(f"Current ledger time (human): {format_ripple_time(ripple_time_to_datetime(close_time_ripple))}")
            logger.info(f"Current ledger index: {current_ledger_index}")
            logger.info(f"FinishAfter time (ripple): {finish_after_time}")
            logger.info(f"FinishAfter time (human): {format_ripple_time(ripple_time_to_datetime(finish_after_time))}")
            logger.info(f"Time difference (seconds): {close_time_ripple - finish_after_time}")

            # Timing check for FinishAfter
            if finish_after_time >= close_time_ripple - 60:
                raise ValueError(
                    f"Escrow cannot be finished yet. FinishAfter: {finish_after_time} ({format_ripple_time(ripple_time_to_datetime(finish_after_time))}), Ledger time: {close_time_ripple} ({format_ripple_time(ripple_time_to_datetime(close_time_ripple))}), Time difference: {close_time_ripple - finish_after_time} seconds")

            # Warn about CancelAfter but proceed
            if cancel_after_time and close_time_ripple > cancel_after_time:
                logger.warning(f"Ledger time {close_time_ripple} is past CancelAfter {cancel_after_time} ({format_ripple_time(ripple_time_to_datetime(cancel_after_time))}). Escrow object exists, attempting to finish.")

            # Build EscrowFinish transaction
            finish_tx = create_finish_escrow_transaction(submit_account, creator_wallet.address, int(offer_sequence), condition, fulfillment, account_sequence, str(fee), current_ledger_index)
            logger.info(f"EscrowFinish transaction (pre-sign): {finish_tx.to_dict()}")

            # Sign and submit
            signed_tx = sign(finish_tx, submit_wallet)
            logger.info(f"Signed transaction: {signed_tx.to_dict()}")
            submit_start = time.time()
            finish_escrow_transaction_response = submit_and_wait(signed_tx, self.client)
            logger.info(f"Submission took {time.time() - submit_start} seconds")
            logger.info(f"Full transaction response: {finish_escrow_transaction_response.result}")
            validate_response(finish_escrow_transaction_response, "Escrow finish failed")
            logger.info(f"Ledger index at submission: {self.client.request(Ledger(ledger_index='current')).result['ledger_current_index']}")

            return create_finish_escrow_time_based_response(finish_escrow_transaction_response.result)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class CancelEscrow(BaseXRPLView):
    def __init__(self):
        super().__init__()

    def post(self, request):
        return self.cancel_escrow(request)

    def get(self, request):
        return self.cancel_escrow(request)

    def cancel_escrow(self, request):
        start_time = time.time()
        function_name = 'cancel_escrow'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Parse request data
            data = json.loads(request.body)
            escrow_creator_seed = data.get("escrow_creator_seed")
            tx_hash = data.get("tx_hash")

            # Validate seed
            if not is_valid_xrpl_seed(escrow_creator_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            # Create sender wallet
            sender_wallet = Wallet.from_seed(escrow_creator_seed)

            tx_response = self.client.request(prepare_tx(tx_hash))
            validate_response(tx_response, "Failed to fetch escrow transaction")

            tx_data = tx_response.result['tx_json']
            if "Sequence" not in tx_data or "Account" not in tx_data:
                raise XRPLException(error_response("EscrowCreate transaction not found or invalid"))

            escrow_sequence = tx_data['Sequence']
            escrow_creator_account = tx_data['Account']
            logger.info(f"Escrow Sequence: {escrow_sequence}, Creator Account: {escrow_creator_account}")

            # Check CancelAfter time if present
            if "CancelAfter" in tx_data:
                ledger_response = self.client.request(Ledger(ledger_index="validated"))
                validate_response(ledger_response, "Failed to fetch ledger data")

                current_ledger_time = ledger_response.result["ledger"]["close_time"]
                if current_ledger_time < tx_data["CancelAfter"]:
                    raise XRPLException(error_response(f"Cannot cancel yet; CancelAfter time ({tx_data['CancelAfter']}) not reached"))

            # Fetch fee and ledger index
            base_fee = get_base_fee(self.client)
            current_ledger_index = get_ledger_index(self.client, "validated")

            # Build, sign, and submit transaction
            cancel_tx = create_cancel_escrow_transaction(sender_wallet.address, escrow_sequence, base_fee, current_ledger_index)
            logger.info("Signing and submitting escrow cancel transaction")
            tx_response = submit_and_wait(cancel_tx, self.client, sender_wallet)
            validate_response(tx_response, "Escrow cancellation failed")

            # Return response
            return create_escrow_cancel_response(tx_response.result)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
