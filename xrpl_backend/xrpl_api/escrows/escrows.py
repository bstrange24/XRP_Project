import logging
import time
from decimal import Decimal

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.clients import XRPLRequestFailureException
from xrpl.core.addresscodec import XRPLAddressCodecException
from xrpl.models import Ledger, Fee, AccountInfo
from xrpl.transaction import submit_and_wait
from xrpl.utils import drops_to_xrp, ripple_time_to_datetime
from xrpl.wallet import generate_faucet_wallet, Wallet
from xrpl.utils import datetime_to_ripple_time, xrp_to_drops

from .escrows_util import create_escrow_transaction, create_escrow_account_transaction, \
    create_cancel_escrow_transaction, create_finish_escrow_transaction, get_escrow_account_response, \
    get_escrow_tx_id_account_response, generate_escrow_condition_and_fulfillment, create_escrow_account_response
from ..constants.constants import ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, INVALID_WALLET_IN_REQUEST, \
    ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, SENDER_SEED_IS_INVALID, MISSING_REQUEST_PARAMETERS, INVALID_TX_ID_IN_REQUEST
from ..errors.error_handling import process_transaction_error, handle_error_new, error_response
from ..transactions.transactions_util import prepare_tx
from ..utilities.utilities import get_xrpl_client, \
    total_execution_time_in_millis, validate_xrp_wallet, is_valid_xrpl_seed, validate_xrpl_response_data, \
    is_valid_txn_id_format, does_txn_exist

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class EscrowAccount(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.get_account_escrow(request)

    def get(self, request, *args, **kwargs):
        return self.get_account_escrow(request)

    def get_account_escrow(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'get_account_escrow'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        get_escrow_from_account = False
        get_escrow_from_txn_id = False

        try:
            account = self.request.GET.get('account')
            prev_txn_id = self.request.GET.get('prev_txn_id')

            # Check if both parameters are missing
            if not account and not prev_txn_id:
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            # Validate account if provided
            if account:
                if not validate_xrp_wallet(account):
                    raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))
                if not does_account_exist(account, self.client):
                    raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            # Set flags based on parameters
            if prev_txn_id and not account:
                get_escrow_from_txn_id = True
            elif account and not prev_txn_id:
                get_escrow_from_account = True
            else:
                # If both parameters are provided, prioritize `account` over `prev_txn_id`
                get_escrow_from_account = True

            if get_escrow_from_txn_id and (not is_valid_txn_id_format(prev_txn_id) or not does_txn_exist(prev_txn_id, self.client)):
                raise XRPLException(error_response(INVALID_TX_ID_IN_REQUEST))

            if get_escrow_from_account:
                logger.info(f"Getting escrow based on account: {get_escrow_from_account}")
                all_escrows_dict = {}
                sent_escrows = []
                received_escrows = []

                # Build and make request
                escrow_account_request = create_escrow_account_transaction(account)
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
                        if escrow_data["sender"] == account:
                            sent_escrows.append(escrow_data)
                        else:
                            received_escrows.append(escrow_data)

                # Add lists to escrow dict
                all_escrows_dict["sent"] = sent_escrows
                all_escrows_dict["received"] = received_escrows

                return get_escrow_account_response(all_escrows_dict)
            else:
                logger.info(f"Getting escrow based on txn id: {get_escrow_from_txn_id}")
                # Build and send query for PreviousTxnID
                transaction_id_request = prepare_tx(prev_txn_id)
                transaction_id_response = self.client.request(transaction_id_request)

                # Validate client response. Raise exception on error
                if validate_xrpl_response_data(transaction_id_response):
                    process_transaction_error(transaction_id_response)

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
            logger.error(f"XRPL error: {str(e)}")
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
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
            receiving_account = self.request.GET.get('account')
            sender_seed = self.request.GET.get('sender_seed')
            amount_to_escrow = self.request.GET.get('amount_to_escrow')

            if not all([receiving_account, sender_seed, amount_to_escrow]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not receiving_account and not validate_xrp_wallet(receiving_account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            if not does_account_exist(receiving_account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(receiving_account)))

            # Escrow will be available to claim after 3 days
            claim_date = datetime_to_ripple_time(datetime.now() + timedelta(days=3))

            # Escrow will expire after 5 days
            expiry_date = datetime_to_ripple_time(datetime.now() + timedelta(days=5))

            # Optional field
            # You can optionally use a Crypto Condition to allow for dynamic release of funds. For example:
            # condition = "A02580205A0E9E4018BE1A6E0F51D39B483122EFDF1DDEF3A4BE83BE71522F9E8CDAB179810120"  # do not use in production
            condition, fulfillment = generate_escrow_condition_and_fulfillment()

            # sender wallet object
            sender_wallet = Wallet.from_seed(sender_seed)

            account_info = self.client.request(AccountInfo(account=sender_wallet.classic_address))
            sequence = account_info.result["account_data"]["Sequence"]
            fee_response = self.client.request(Fee())
            fee = fee_response.result["drops"]["base_fee"]
            ledger_response = self.client.request(Ledger(ledger_index="current"))
            current_ledger = ledger_response.result["ledger_current_index"]

            # Build escrow create transaction
            create_escrow_txn = create_escrow_transaction(sender_wallet.address, Decimal(amount_to_escrow), receiving_account, condition,
                                                          sequence, fee, current_ledger)

            # Autofill, sign, then submit transaction and wait for result
            create_escrow_transaction_response = submit_and_wait(create_escrow_txn, self.client, sender_wallet)

            # Validate client response. Raise exception on error
            if validate_xrpl_response_data(create_escrow_transaction_response):
                process_transaction_error(create_escrow_transaction_response)

            # Return result of transaction
            create_escrow_transaction_result = create_escrow_transaction_response.result

            # Parse result and print out the necessary info
            print(create_escrow_transaction_result["tx_json"]["Account"])
            print(create_escrow_transaction_result["tx_json"]["Sequence"])

            print(create_escrow_transaction_result["meta"]["TransactionResult"])
            print(create_escrow_transaction_result["hash"])

            return create_escrow_account_response(create_escrow_transaction_result)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            logger.error(f"XRPL error: {str(e)}")
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class CancelEscrow(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.cancel_escrows(request)

    def get(self, request, *args, **kwargs):
        return self.cancel_escrows(request)

    def cancel_escrows(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'cancel_escrows'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            receiving_account = self.request.GET.get('account')
            sender_seed = self.request.GET.get('sender_seed')

            if not is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not receiving_account and not validate_xrp_wallet(receiving_account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            if not does_account_exist(receiving_account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(receiving_account)))

            escrow_sequence = 30215126

            # sender wallet object
            sender_wallet = Wallet.from_seed(sender_seed)

            # Build escrow cancel transaction
            cancel_txn = create_cancel_escrow_transaction(sender_wallet.address, escrow_sequence)

            # Autofill, sign, then submit transaction and wait for result
            stxn_response = submit_and_wait(cancel_txn, self.client, sender_wallet)

            # Parse response and return result
            stxn_result = stxn_response.result

            # Parse result and print out the transaction result and transaction hash
            print(stxn_result["meta"]["TransactionResult"])
            print(stxn_result["hash"])

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            logger.error(f"XRPL error: {str(e)}")
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class FinishEscrow(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.finish_escrows(request)

    def get(self, request, *args, **kwargs):
        return self.finish_escrows(request)

    def finish_escrows(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'finish_escrows'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            escrow_account = self.request.GET.get('escrow_account')
            sender_seed = self.request.GET.get('sender_seed')

            if not is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not escrow_account and not validate_xrp_wallet(escrow_account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            if not does_account_exist(escrow_account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(escrow_account)))

            escrow_sequence = 30215126

            # Crypto condition that must be met before escrow can be completed, passed on escrow creation
            condition = "A02580203882E2EB9B44130530541C4CC360D079F265792C4A7ED3840968897CB7DF2DA1810120"

            # Crypto fulfillment of the condtion
            fulfillment = "A0228020AED2C5FE4D147D310D3CFEBD9BFA81AD0F63CE1ADD92E00379DDDAF8E090E24C"

            # sender wallet object
            sender_wallet = Wallet.from_seed(sender_seed)

            # Build escrow finish transaction
            finish_txn = create_finish_escrow_transaction(sender_wallet.address, escrow_account,
                                      escrow_sequence,condition,fulfillment)

            # Autofill, sign, then submit transaction and wait for result
            stxn_response = submit_and_wait(finish_txn, self.client, sender_wallet)

            # Parse response and return result
            stxn_result = stxn_response.result

            # Parse result and print out the transaction result and transaction hash
            print(stxn_result["meta"]["TransactionResult"])
            print(stxn_result["hash"])

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            logger.error(f"XRPL error: {str(e)}")
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
