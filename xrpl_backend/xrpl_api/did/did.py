import json
import logging
import time

from django.views import View
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.transaction import submit_and_wait
from xrpl.wallet import Wallet

from .did_util import prepare_ledger_entry, did_response, prepare_did_set, set_did_response, prepare_did_delete, \
    delete_did_response, validate_did_set_data
from ..constants.constants import ENTERING_FUNCTION_LOG, ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, \
    INVALID_WALLET_IN_REQUEST, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, SENDER_SEED_IS_INVALID, MISSING_REQUEST_PARAMETERS
from ..errors.error_handling import process_transaction_error, error_response, handle_error_new
from ..utilities.utilities import get_xrpl_client, total_execution_time_in_millis, validate_xrpl_response_data, \
    validate_xrp_wallet, is_valid_xrpl_seed

logger = logging.getLogger('xrpl_app')


class GetDid(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request):
        return self.get_did(request)

    def get(self, request):
        return self.get_did(request)

    def get_did(self, request):
        start_time = time.time()  # Capture the start time to track the execution duration.
        function_name = 'get_did'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log function entry.

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            data = json.loads(request.body)
            account = data.get("account")

            # Validate the provided wallet address
            if not account or not validate_xrp_wallet(account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            if not does_account_exist(account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            # build the request for the account's DID
            ledger_entry = prepare_ledger_entry(account, "validated")

            # submit request and awaiting result
            logger.info(f"signed and submitting did delete transaction. awaiting response...")
            response = self.client.request(ledger_entry)

            # parse result
            if "index" in response.result and "Account" in response.result["node"]:
                logger.info(f'DID index: {response.result["node"]["index"]}')
                logger.info(f'DID Document: {response.result["node"]["DIDDocument"]}')
                logger.info(f'Data: {response.result["node"]["Data"]}')
                logger.info(f'URI: {response.result["node"]["URI"]}')
                return did_response(response.result, True)
            else:
                logger.info("No DID found for this account")
                return did_response(response.result, False)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


class SetDid(View):
    def __init__(self):
        super().__init__()
        self.client = None

    def post(self, request):
        return self.set_did(request)

    def get(self, request):
        return self.set_did(request)

    def set_did(self, request):
        start_time = time.time()
        function_name = 'set_did'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            data = json.loads(request.body)
            account_seed = data.get("account_seed")
            # define the document associated with the DID
            document = data.get("document")
            # The public attestations of identity credentials associated with the DID.
            did_data = data.get("did_data")
            # The Universal Resource Identifier associated with the DID.
            uri = data.get("uri")

            required_fields = ["account_seed", "document"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(account_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            logger.info(f"Document: {document} Data: {did_data} URI: {uri}")

            result, message = validate_did_set_data(did_data, uri)
            if not result:
                raise XRPLException(error_response(message))

            account_did_creator = Wallet.from_seed(account_seed)

            logger.info(f"Successfully retrieved wallet: {account_did_creator.classic_address}")

            # build DID SET transaction
            did_set_txn = prepare_did_set(account_did_creator.address, document, did_data, uri)

            # sign, submit the transaction and wait for the response
            logger.info("signing and submitting the transaction, awaiting a response")
            did_set_txn_response = submit_and_wait(did_set_txn, self.client, account_did_creator)

            if validate_xrpl_response_data(did_set_txn_response):
                process_transaction_error(did_set_txn_response)

            logger.info(did_set_txn_response.result["meta"]["TransactionResult"])
            logger.info(did_set_txn_response.result["hash"])

            return set_did_response(did_set_txn_response.result)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


class DeleteDid(View):
    def __init__(self):
        super().__init__()
        self.client = None

    def post(self, request):
        return self.delete_did(request)

    def get(self, request):
        return self.delete_did(request)

    def delete_did(self, request):
        start_time = time.time()  # Capture the start time of the function execution.
        function_name = 'delete_did'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function.

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            # Extract wallet address from request parameters
            data = json.loads(request.body)
            account_seed = data.get("account_seed")

            required_fields = ["account_seed"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(account_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            # restore an account that has an existing DID
            account_did_creator = Wallet.from_seed(account_seed)

            # define the account DIDDelete transaction
            did_delete_txn = prepare_did_delete(account_did_creator.address)

            # sign, submit the did delete transaction and wait for result
            logger.info(f"signed and submitting did delete transaction. awaiting response...")
            did_delete_response = submit_and_wait(did_delete_txn, self.client, account_did_creator)

            if validate_xrpl_response_data(did_delete_response):
                process_transaction_error(did_delete_response)

            logger.info(did_delete_response.result["meta"]["TransactionResult"])
            logger.info(did_delete_response.result["hash"])

            return delete_did_response(did_delete_response.result)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
