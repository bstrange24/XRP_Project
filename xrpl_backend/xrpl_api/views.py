import xrpl
import json
import logging
import time

from django.core.paginator import Paginator
from django.core.cache import cache
from rest_framework.pagination import PageNumberPagination
from django.http import JsonResponse
from xrpl.clients import JsonRpcClient
from xrpl.models import AccountTx, Tx, AccountDelete, Payment, AccountLines, AccountOffers, ServerInfo, TrustSet
from xrpl.wallet import generate_faucet_wallet
from xrpl.core import addresscodec
from xrpl.utils import xrp_to_drops, drops_to_xrp
from xrpl.wallet import Wallet
from xrpl.models.requests import AccountInfo
from xrpl.models.requests import Ledger
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .constants import *
from .db_operations import save_account_data_to_databases
from .models import XrplAccountData, XrplPaymentData
from xrpl.transaction import submit_and_wait
from xrpl.models.transactions import AccountSet
from decimal import Decimal
from .utils import validate_account_id, get_xrpl_client, handle_error, get_account_reserves, validate_transaction_hash, \
    check_for_none

logger = logging.getLogger('xrpl_app')

# Constants for flags
# REQUIRE_DESTINATION_TAG_FLAG = 0x00010000  # 0x00010000: Require Destination Tag
# DISABLE_MASTER_KEY_FLAG = 0x00040000  # 0x00040000: Disable Master Key
# ENABLE_REGULAR_KEY_FLAG = 0x00080000  # 0x00080000: Enable Regular Key
# MAX_RETRIES = 3  # Maximum retry attempts
# RETRY_BACKOFF = 2  # Exponential backoff base in seconds
# PAGINATION_PAGE_SIZE = 10

class AccountInfoPagination(PageNumberPagination):
    page_size = PAGINATION_PAGE_SIZE

def create_account(request):
    function_name = 'create_account'
    logger.info(f"Entering: {function_name}")

    retries = 0  # Retry attempt counter

    while retries <= MAX_RETRIES:
        try:
            client = get_xrpl_client()
            check_for_none(client, function_name, "Error client initialization failed.")

            new_wallet = generate_faucet_wallet(client, debug=True)
            check_for_none(new_wallet, function_name, "Error creating new wallet. Wallet is empty")

            test_account = new_wallet.address
            test_xaddress = addresscodec.classic_address_to_xaddress(test_account, tag=12345, is_test_network=True)
            logger.debug(f"Classic address: {test_account}")
            logger.debug(f"X-address: {test_xaddress}")

            account_info_request = AccountInfo(
                account=test_account,
                ledger_index="validated",
                strict=True,
            )
            check_for_none(account_info_request, function_name, "Error creating Account Info.")

            response = client.request(account_info_request)
            check_for_none(response, function_name, "Response is none.")

            if response.status == 'success':
                logger.info(f"response.status: {response.status}")

                result = response.result

                logger.debug(f"Raw XRPL response:")
                logger.debug(json.dumps(result, indent=4, sort_keys=True))

                # Convert drops to XRP
                balance_drops = response.result['account_data']['Balance']
                balance = drops_to_xrp(str(balance_drops))
                balance = round(balance, 2)

                ledger_hash = result['ledger_hash']

                # Save account to the database
                save_account_data_to_databases(result, balance)

                return JsonResponse({
                    'status': 'success',
                    'message': 'Successfully created wallet.',
                    'account_id': new_wallet.address,
                    'secret': new_wallet.seed,
                    'balance': balance,
                    'transaction_hash':ledger_hash,
                })
            else:
                return handle_error({'status': 'failure', 'message': f"Failed to fund account via faucet: {response.text}"}, status_code=500, function_name=function_name)
        except (xrpl.XRPLException, ConnectionError, ValueError, Exception) as e:
            logger.error(f"Attempt {retries + 1} - Error: {str(e)}")
            if retries == MAX_RETRIES:
                # If max retries reached, return error response
                logger.error(f"Max retry attempts reached for account creation.")
                return handle_error({'status': 'failure', 'message': f"Error creating new wallet: {str(e)}"}, status_code=500, function_name=function_name)

            # Exponential backoff logic
            backoff_time = RETRY_BACKOFF * (2 ** retries)  # Exponential backoff
            logger.info(f"Retrying in {backoff_time} seconds...")
            time.sleep(backoff_time)  # Wait before retrying

            retries += 1  # Increment the retry count
        # except ValueError as ve:
        #     return handle_error({'status': 'failure', 'message': f"ValueError: {str(ve)}"}, status_code=500, function_name=function_name)
        # except Exception as e:
        #     return handle_error({'status': 'failure', 'message': f"Error creating new wallet: {str(e)}"}, status_code=500, function_name=function_name)

def get_wallet_info(request, wallet_address):
    function_name = 'get_wallet_info'
    logger.info(f"Entering: {function_name}")

    # Validate the account ID format
    if not validate_account_id(wallet_address):
        return handle_error({'status': 'failure', 'message': 'Invalid address format.'}, status_code=400,
                            function_name=function_name)

    # Retry logic initialization
    retries = 0

    while retries <= MAX_RETRIES:
        try:
            # Log the account ID being queried
            logger.info(f"Fetching account info for: {wallet_address}")

            # Connect to the XRPL Testnet
            client = get_xrpl_client()
            check_for_none(client, function_name, "Error client initialization failed.")

            # Create an AccountInfo request
            account_info_request = AccountInfo(
                account=wallet_address,
                ledger_index="validated"
            )
            check_for_none(account_info_request, function_name, "Error creating Account Info.")

            # Send the request to the XRPL
            response = client.request(account_info_request)
            check_for_none(response, function_name, "Response is none.")

            result = response.result

            # Log the raw response for debugging
            logger.debug(f"Raw XRPL response:")
            logger.debug(json.dumps(result, indent=4, sort_keys=True))

            # Check if the request was successful
            if response.is_successful():
                current_sequence = response.result['account_data']['Sequence']

                balance = response.result['account_data']['Balance']
                balance = drops_to_xrp(str(balance))
                balance = round(balance, 2)

                logger.debug(f"Getting reserves")
                base_reserve, reserve_increment = get_account_reserves()
                if base_reserve is not None and reserve_increment is not None:
                    logger.debug(f"Base reserve in XRP: {base_reserve} XRP")
                    logger.debug(f"Reserve increment per object in XRP: {reserve_increment} XRP")
                else:
                    return handle_error({'status': 'failure', 'message': 'Failed to fetch reserve data.'}, status_code=500,function_name=function_name)

                logger.info(f"Account found: {wallet_address}, Balance: {balance}, Base Reserve: {base_reserve}, Reserve Increment: {reserve_increment}")
                return JsonResponse({
                    'status': 'success',
                    'message': 'Successfully retrieved account information.',
                    'reserve': base_reserve,
                    'reserve_increment': reserve_increment,
                    'result': result,
                })
            else:
                return handle_error({'status': 'failure', 'message': 'Account not found on XRPL.'}, status_code=404, function_name=function_name)
        except (xrpl.XRPLException, ConnectionError, ValueError, Exception) as e:
            # Handle exceptions and log errors
            logger.error(f"Attempt {retries + 1} - Error: {str(e)}")
            if retries == MAX_RETRIES:
                # If max retries reached, return error response
                logger.error(f"Max retry attempts reached for address {wallet_address}.")
                return handle_error({'status': 'failure', 'message': f"Error fetching account info: {str(e)}"}, status_code=500, function_name=function_name)

            # Exponential backoff logic
            backoff_time = RETRY_BACKOFF * (2 ** retries)  # Exponential backoff
            logger.info(f"Retrying in {backoff_time} seconds...")
            time.sleep(backoff_time)  # Wait before retrying

            retries += 1  # Increment the retry count
        # except ValueError as ve:
        #     return handle_error({'status': 'failure', 'message': f"ValueError: {str(ve)}"}, status_code=400, function_name=function_name)
        # except Exception as e:
        #     return handle_error({'status': 'failure', 'message': f"Error fetching account info: {str(e)}"}, status_code=500, function_name=function_name)

def check_wallet_balance(request, wallet_address):
    function_name = 'check_wallet_balance'
    logger.info(f"Entering: {function_name}")

    # Validate the address format
    if not validate_account_id(wallet_address):
        return handle_error({'status': 'failure', 'message': 'Invalid address format.'}, status_code=400, function_name=function_name)

    # Log the start of the check balance request
    logger.info(f"Request received to check balance for address: {wallet_address}")

    # Retry logic initialization
    retries = 0

    while retries <= MAX_RETRIES:
        try:
            # Get the XRPL client
            client = get_xrpl_client()
            check_for_none(client, function_name, "Error client initialization failed.")

            # Create an AccountInfo request
            account_info_request = AccountInfo(
                account=wallet_address
            )
            check_for_none(account_info_request, function_name, "Error creating Account Info.")

            # Send the request to the XRPL client
            logger.info(f"Sending account info request for address: {wallet_address}")
            response = client.request(account_info_request)
            check_for_none(response, function_name, "Response is none.")

            # Check if the request was successful
            if response.is_successful():
                # Extract the balance in drops and convert to XRP
                balance_in_drops = int(response.result["account_data"]["Balance"])
                balance_in_xrp = drops_to_xrp(str(balance_in_drops))

                # Log the successful balance retrieval
                logger.info(f"Balance for address {wallet_address} retrieved successfully: {balance_in_xrp} XRP")

                # Return the balance as JSON response
                return JsonResponse({
                    'status': 'success',
                    'message': 'Successfully retrieved account balance.',
                    "balance": balance_in_xrp,
                })
            else:
                # Log the failure to fetch account info
                return handle_error({'status': 'failure', 'message': 'Account not found on XRPL.'}, status_code=404, function_name=function_name)
        except (xrpl.XRPLException, ConnectionError, ValueError, Exception) as e:
            # Handle exceptions and log errors
            logger.error(f"Attempt {retries + 1} - Error: {str(e)}")
            if retries == MAX_RETRIES:
                # If max retries reached, return error response
                logger.error(f"Max retry attempts reached for address {wallet_address}.")
                return handle_error({'status': 'failure', 'message': f"Error fetching account info: {str(e)}"}, status_code=500, function_name=function_name)

            # Exponential backoff logic
            backoff_time = RETRY_BACKOFF * (2 ** retries)  # Exponential backoff
            logger.info(f"Retrying in {backoff_time} seconds...")
            time.sleep(backoff_time)  # Wait before retrying

            retries += 1  # Increment the retry count

def account_set(request):
    function_name = 'account_set'
    logger.info(f"Entering: {function_name}")

    retries = 0  # Retry attempt counter

    while retries <= MAX_RETRIES:
        try:
            # Extract and validate parameters from the request
            sender_seed = request.GET.get('sender_seed')
            check_for_none(sender_seed, function_name, "Missing sender_seed parameter.")

            require_destination_tag = request.GET.get('require_destination_tag', 'false').lower() == 'true'
            disable_master_key = request.GET.get('disable_master_key', 'false').lower() == 'true'
            enable_regular_key = request.GET.get('enable_regular_key', 'false').lower() == 'true'

            # Log the passed in account setting values
            logger.info(f"require_destination_tag: {require_destination_tag}, disable_master_key: {disable_master_key}, enable_regular_key: {enable_regular_key}")

            # Create the wallet from the sender seed
            sender_wallet = Wallet.from_seed(sender_seed)
            sender_address = sender_wallet.classic_address

            flags = build_flags(require_destination_tag, disable_master_key, enable_regular_key)
            # # Build the flags you want to set
            # flags = 0
            #
            # # Enable or disable the requireDestinationTag flag
            # if require_destination_tag:
            #     flags |= 0x00010000  # 0x00010000: Require Destination Tag
            #
            # # Disable master key
            # if disable_master_key:
            #     flags |= 0x00040000  # 0x00040000: Disable Master Key
            #
            # # Enable regular key
            # if enable_regular_key:
            #     flags |= 0x00080000  # 0x00080000: Enable Regular Key

            # Create the AccountSet transaction
            account_set_tx = AccountSet(
                account=sender_address,
                flags=flags
            )
            check_for_none(account_set_tx, function_name, "Error creating Account Set.")

            # Get the client to communicate with XRPL
            client = get_xrpl_client()
            check_for_none(client, function_name, "Error client initialization failed.")

            # Submit the transaction
            response = submit_and_wait(account_set_tx, client, sender_wallet)
            check_for_none(response, function_name, "Error submit_and_wait return None.")

            # Check if the transaction was successful
            if response.is_successful():
                logger.info(f"AccountSet transaction successful for account {sender_address}")
                return JsonResponse({
                    'status': 'success',
                    'message': 'Successfully updated account settings.',
                    'transaction_hash': response.result['hash'],
                    'account': sender_address,
                    'settings': response.result
                })

            else:
                return handle_error({'status': 'failure', 'message': f"AccountSet transaction failed for account {sender_address}. Response: {response}"}, status_code=500, function_name=function_name)
        except (xrpl.XRPLException, ConnectionError, ValueError, Exception) as e:
            logger.error(f"Attempt {retries + 1} - Error: {str(e)}")

            # If max retries reached, return error response
            if retries == MAX_RETRIES:
                logger.error(f"Max retry attempts reached for account set operation.")
                return handle_error({'status': 'failure', 'message': f"Error updating account settings: {str(e)}"}, status_code=500, function_name=function_name)

            # Exponential backoff logic
            backoff_time = RETRY_BACKOFF * (2 ** retries)  # Exponential backoff
            logger.info(f"Retrying in {backoff_time} seconds...")
            time.sleep(backoff_time)  # Wait before retrying

            retries += 1  # Increment the retry count
        # except ValueError as ve:
        #     error_msg = f"ValueError: {str(ve)}"
        #     return handle_error({'status': 'failure', 'message': f"ValueError: {str(ve)}"}, status_code=400, function_name=function_name)
        # except Exception as e:
        #     return handle_error({'status': 'failure', 'message': f"Error fetching account info: {str(e)}"}, status_code=500, function_name=function_name)

def get_transaction_history(request, wallet_address, transaction_hash):
    function_name = 'get_transaction_history'
    logger.info(f"Entering: {function_name}")

    if not validate_account_id(wallet_address):
        return handle_error({'status': 'failure', 'message': 'Invalid address format.'}, status_code=400, function_name=function_name)

    if not validate_transaction_hash(transaction_hash):
        return handle_error({'status': 'failure', 'message': 'Invalid address format.'}, status_code=400, function_name=function_name)

    retries = 0  # Retry attempt counter

    while retries <= MAX_RETRIES:
        try:
            client = get_xrpl_client()
            check_for_none(client, function_name, "Error client initialization failed.")

            # Create an AccountTx request
            account_tx_request = AccountTx(
                account=wallet_address,
                limit=1
            )
            check_for_none(account_tx_request, function_name, "Error getting AccountTx.")

            # Submit the request to the XRPL
            response = client.request(account_tx_request)
            check_for_none(response, function_name, "Response is none.")

            # Check if the response contains transactions
            if 'transactions' in response.result:
                transactions = response.result['transactions']

                # Search for the transaction with the specific hash
                for transaction in transactions:
                    if transaction['hash'] == transaction_hash:
                        logger.debug("Transaction found:", transaction)

                        logger.debug(json.dumps(transaction, indent=4, sort_keys=True))

                        # Return the transaction history  response.result['transactions'][0]['hash']
                        # return JsonResponse(response.result)
                        return JsonResponse({
                            'status': 'success',
                            'message': 'Transaction history successfully retrieved.',
                            'response': transaction,
                        })
            else:
                return handle_error({'status': 'failure', 'message': f"Error fetching transaction history info"},
                                    status_code=500, function_name=function_name)

            # Log the response
            logger.info(f"Transaction history fetched for address: {wallet_address}")
        except (xrpl.XRPLException, ConnectionError, ValueError, Exception) as e:
            logger.error(f"Attempt {retries + 1} - Error: {str(e)}")

            # If max retries reached, return error response
            if retries == MAX_RETRIES:
                logger.error(f"Max retry attempts reached for fetching transaction history.")
                return handle_error(
                    {'status': 'failure', 'message': f"Error fetching transaction history info: {str(e)}"}, status_code=500, function_name=function_name)

            # Exponential backoff logic
            backoff_time = RETRY_BACKOFF * (2 ** retries)  # Exponential backoff
            logger.info(f"Retrying in {backoff_time} seconds...")
            time.sleep(backoff_time)  # Wait before retrying

            retries += 1  # Increment the retry count
        # except Exception as e:
        #     return handle_error({'status': 'failure', 'message': f"Error fetching transaction history info: {e}"}, status_code=500, function_name=function_name)

@api_view(['GET'])
def get_transaction_history_with_pagination(request, wallet_address):
    function_name = 'get_transaction_history_with_pagination'
    logger.info(f"Entering: {function_name}")

    if not validate_account_id(wallet_address):
        return handle_error({'status': 'failure', 'message': 'Invalid address format.'}, status_code=400, function_name=function_name)

    retries = 0  # Retry attempt counter
    transactions = []
    marker = None

    while retries <= MAX_RETRIES:
        try:
            client = get_xrpl_client()
            check_for_none(client, function_name, "Error client initialization failed.")

            while True:
                account_tx_request = AccountTx(
                    account=wallet_address,
                    ledger_index_min=-1,
                    ledger_index_max=-1,
                    limit=100,
                    marker=marker,
                )
                check_for_none(account_tx_request, function_name, "Error getting AccountTx.")

                response = client.request(account_tx_request)
                check_for_none(response, function_name, "Response is none.")

                transactions.extend(response.result["transactions"])
                logger.debug(json.dumps(response.result["transactions"], indent=4, sort_keys=True))

                # Check if there are more transactions to fetch
                marker = response.result.get("marker")
                if not marker:
                    break

            # Get pagination parameters from request
            # page = int(request.GET.get('page'))
            # if not page:
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 10))
            paginator = Paginator(transactions, page_size)
            paginated_transactions = paginator.get_page(page)

            data = {
                "transactions": list(paginated_transactions),
                "total_transactions": paginator.count,
                "pages": paginator.num_pages,
                "current_page": paginated_transactions.number,
            }

            logger.info(f"Transaction history fetched for address: {wallet_address}")
            return JsonResponse(data)
            # return JsonResponse({
            #     'status': 'success',
            #     'message': 'Transaction history successfully retrieved.',
            #     'transactions': data,
            # })
        except (xrpl.XRPLException, ConnectionError, ValueError, Exception) as e:
            logger.error(f"Attempt {retries + 1} - Error: {str(e)}")

            # If retries exhausted, return error
            if retries == MAX_RETRIES:
                logger.error(f"Max retry attempts reached for fetching transaction history.")
                return handle_error({'status': 'failure', 'message': f"Error fetching transaction history info: {str(e)}"}, status_code=500, function_name=function_name)

            # Exponential backoff logic
            backoff_time = RETRY_BACKOFF * (2 ** retries)  # Exponential backoff
            logger.info(f"Retrying in {backoff_time} seconds...")
            time.sleep(backoff_time)  # Wait before retrying

            retries += 1  # Increment the retry count
    # except Exception as e:
    #     return handle_error({'status': 'failure', 'message': f"Error fetching transaction history info: {e}"}, status_code=500, function_name=function_name)

def check_transaction_status(request, tx_hash):
    function_name = 'check_transaction_status'
    logger.info(f"Entering: {function_name}")

    check_for_none(tx_hash, function_name, "Error transaction hash is None.")

    retries = 0  # Retry attempt counter

    while retries <= MAX_RETRIES:
        try:
            # Log the start of the transaction status check
            logger.info(f"Checking transaction status for hash: {tx_hash}")

            # Get the XRPL client
            client = get_xrpl_client()
            check_for_none(client, function_name, "Error client initialization failed.")

            # Create a transaction request
            tx_request  = Tx(transaction=tx_hash)
            check_for_none(tx_request, function_name, "Trasnaction Tx is none.")

            # Send the request to the XRPL
            response = client.request(tx_request )
            check_for_none(response, function_name, "Response is none.")

            # Log the raw response for debugging
            logger.info(f"Raw XRPL response for transaction {tx_hash}: {response}")

            # Check if the request was successful
            if response.is_successful():
                # Log the successful retrieval of transaction status
                logger.info(f"Transaction status retrieved successfully for hash: {tx_hash}")
                # return JsonResponse(response.result)
                return JsonResponse({
                    'status': 'success',
                    'message': 'Payment successfully sent.',
                    'response.result': response.result,
                })
            else:
                # Log the failure to retrieve transaction status
                return handle_error({'status': 'failure', 'message': 'Error retrieving transaction status.'}, status_code=400, function_name=function_name)
        except (xrpl.XRPLException, ConnectionError, ValueError, Exception) as e:
            # Log error and attempt retry if max retries not reached
            logger.error(
                f"Attempt {retries + 1} - Error while checking transaction status for hash {tx_hash}: {str(e)}")

            if retries == MAX_RETRIES:
                logger.error(f"Max retry attempts reached for checking transaction status for hash {tx_hash}.")
                return handle_error({'status': 'failure', 'message': f"Error while checking transaction status for hash {tx_hash}: {str(e)}"}, status_code=500, function_name=function_name)

            # Exponential backoff for retries
            backoff_time = RETRY_BACKOFF * (2 ** retries)  # Exponential backoff
            logger.info(f"Retrying in {backoff_time} seconds...")
            time.sleep(backoff_time)  # Wait before retrying

            retries += 1  # Increment the retry count

        # except Exception as e:
            # return handle_error({'status': 'failure', 'message': f"Error while checking transaction status for hash {tx_hash}: {e}"}, status_code=500, function_name=function_name)

def send_payment(request):
    function_name = 'send_payment'
    logger.info(f"Entering: {function_name}")

    retries = 0  # Retry attempt counter

    while retries <= MAX_RETRIES:
        try:
            # account = request.GET.get('sender_address')
            sender_seed = request.GET.get('sender_seed')
            receiver_address = request.GET.get('receiver')
            amount_xrp = Decimal(request.GET.get('amount'))

            amount_drops = xrp_to_drops(amount_xrp)

            client = get_xrpl_client()
            check_for_none(client, function_name, "Error client initialization failed.")

            sender_wallet = Wallet.from_seed(sender_seed)
            sender_address = sender_wallet.classic_address

            # Construct the Payment transaction
            payment_transaction = Payment(
                account=sender_address,
                destination=receiver_address,
                amount=amount_drops,
            )
            check_for_none(payment_transaction, function_name, "Payment is None.")

            # Submit the transaction
            payment_response = submit_and_wait(payment_transaction, client, sender_wallet)
            check_for_none(payment_response, function_name, "Error submit_and_wait return None.")

            if payment_response.is_successful():
                transaction_hash = payment_response.result['hash']
                logger.info(f"Payment successful: {transaction_hash}")

                # Save the payment details (assuming you have a Payment model)
                payment = XrplPaymentData(
                    sender=sender_address,
                    receiver=receiver_address,
                    amount=amount_xrp,
                    transaction_hash=transaction_hash,
                )
                payment.save()

                # Update sender and receiver balances (assuming you have an XRPLAccount model)
                # sender_account = XRPLAccount.objects.get(account_id=sender_address)
                sender_account = XrplAccountData.objects.get(account=sender_address)
                sender_account.balance -= amount_xrp
                sender_account.save()

                # receiver_account, created = XRPLAccount.objects.get_or_create(
                receiver_account, created = XrplAccountData.objects.get_or_create(
                    account=receiver_address,
                    defaults={'balance': amount_xrp}
                )
                if not created:
                    receiver_account.balance += amount_xrp
                    receiver_account.save()

                return JsonResponse({
                    'status': 'success',
                    'message': 'Payment successfully sent.',
                    'transaction_hash': transaction_hash,
                    'sender': sender_address,
                    'receiver': receiver_address,
                    'amount': amount_xrp,
                })
            else:
                return handle_error({'status': 'failure', 'message': 'Payment failed.'}, status_code=400, function_name=function_name)
        except (xrpl.XRPLException, ConnectionError, ValueError, Exception) as e:
            logger.error(f"Attempt {retries + 1} - Error sending payment: {e}")

            if retries == MAX_RETRIES:
                logger.error(f"Max retry attempts reached for sending payment. Transaction failed.")
                return handle_error({'status': 'failure', 'message': f"Error sending payment: {str(e)}"}, status_code=500, function_name=function_name)

            # Exponential backoff for retries
            backoff_time = RETRY_BACKOFF * (2 ** retries)  # Exponential backoff
            logger.info(f"Retrying in {backoff_time} seconds...")
            time.sleep(backoff_time)  # Wait before retrying

            retries += 1  # Increment the retry count
        # except Exception as e:
        #     return handle_error({'status': 'failure', 'message': f"Error sending payment: {e}"}, status_code=500, function_name=function_name)

def delete_account(request, wallet_address):
    """
    Check the balance of an XRP wallet, and if the balance is zero,
    submit an AccountDelete transaction to remove the wallet from the ledger.
    """
    function_name = 'delete_account'
    logger.info(f"Entering: {function_name}")

    logger.info(f"Request received to check balance for address: {wallet_address}")

    if not validate_account_id(wallet_address):
        return handle_error({'status': 'failure', 'message': 'Invalid address format.'}, status_code=400, function_name=function_name)

    retries = 0  # Retry attempt counter

    while retries <= MAX_RETRIES:
        # Step 1: Check the wallet balance
        try:
            # Get the sender's seed from the request
            sender_seed = request.GET.get('sender_seed')
            check_for_none(sender_seed, function_name, "Sender seed is required.")

            # if not sender_seed:
            #     return handle_error({'status': 'failure', 'message': 'Sender seed is required.'}, status_code=400, function_name=function_name)

            # Prepare the request to get account info
            account_info_request = AccountInfo(
                account=wallet_address,
                ledger_index="validated",  # Use the latest validated ledger
                strict=True,
            )
            check_for_none(account_info_request, function_name, "Error creating Account Info.")

            # Connect to the XRPL client
            client = get_xrpl_client()
            check_for_none(client, function_name, "Error client initialization failed.")

            # Send the request to XRPL
            response = client.request(account_info_request)
            check_for_none(response, function_name, "Response is none.")

            # Extract the balance from the response
            account_data = response.result
            balance = int(account_data['account_data']['Balance']) / 1_000_000  # Convert drops to XRP

            # Check if balance is zero
            if balance == 0:
                # Step 2: Submit an AccountDelete transaction
                # Prepare the AccountDelete transaction
                account_delete_tx = AccountDelete(
                    account=wallet_address,
                    destination=wallet_address,  # Destination must be the same address for deletion
                    fee="12",  # Standard XRP transaction fee
                )
                check_for_none(account_delete_tx, function_name, "Error creating Account Delete.")

                # Sign the transaction (you need the private key for this)
                signer = xrpl.wallet.Wallet(sender_seed, "False")

                # Step 3: Submit the transaction to the XRPL
                tx_response = xrpl.transaction.sign_and_submit(account_delete_tx, client, signer)
                check_for_none(tx_response, function_name, "Error creating sign_and_submit.")

                # Check if the transaction was successful
                if tx_response.is_successful():
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Account successfully deleted.',
                        'tx_response': tx_response,
                    })
                else:
                    return handle_error({'status': 'failure', 'message': 'Error submitting AccountDelete transaction.', 'details': tx_response.result}, status_code=500, function_name=function_name)
            else:
                return handle_error({'status': 'failure', 'message': 'Balance is not zero, no action taken.'}, status_code=500, function_name=function_name)
        except (xrpl.XRPLException, ConnectionError, ValueError, Exception) as e:
            # Log error and retry on network-related issues
            logger.error(f"Attempt {retries + 1} - Error checking balance or submitting transaction: {e}")

            if retries == MAX_RETRIES:
                logger.error(f"Max retry attempts reached for deleting account {wallet_address}. Transaction failed.")
                return handle_error({'status': 'failure', 'message': f"Error attempting to delete account: {str(e)}"},
                                    status_code=500, function_name=function_name)

            # Exponential backoff for retries
            backoff_time = RETRY_BACKOFF * (2 ** retries)  # Exponential backoff
            logger.info(f"Retrying in {backoff_time} seconds...")
            time.sleep(backoff_time)  # Wait before retrying

            retries += 1  # Increment the retry count

        # except Exception as e:
        #     Catch any other errors
            # return handle_error({'status': 'failure', 'message': f"Error attempting to delete account: {e}"},
            #                     status_code=500, function_name=function_name)
        # except Exception as e:
        #     return handle_error({'status': 'failure', 'message': f"Error attempting to delete account: {e}"}, status_code=500, function_name=function_name)

@api_view(['GET'])
def get_ledger_info(request):
    """
    Fetches information about a specific ledger (by ledger index or hash).
    Uses the 'Ledger' API call to get the latest validated ledger information.
    """
    function_name = 'get_ledger_info'
    logger.info(f"Entering: {function_name}")

    try:
        # Get ledger_index or ledger_hash from the request
        ledger_index = request.GET.get('ledger_index', 'validated')  # Default to 'validated' if not provided
        ledger_hash = request.GET.get('ledger_hash', None)

        # Check cache first before querying the XRPL server
        cache_key = f"ledger_info_{ledger_index}_{ledger_hash or ''}"
        cached_response = cache.get(cache_key)

        if cached_response:
            logger.info(f"Returning cached ledger info for {ledger_index}/{ledger_hash}")
            return JsonResponse(cached_response)

        # Prepare the Ledger request
        if ledger_hash:
            ledger_request = Ledger(ledger_hash=ledger_hash)
        else:
            ledger_request = Ledger(ledger_index=ledger_index)

        # Send the request to XRPL and get the response
        # Instantiate XRPL Client
        client = JsonRpcClient(JSON_RPC_URL)
        response = client.request(ledger_request)

        # Check if the response is successful
        if response.is_successful():
            ledger_info = response.result
            logger.info(f"Successfully retrieved ledger info for {ledger_index}/{ledger_hash}")

            # Prepare the response data
            response_data = {
                'status': 'success',
                'message': 'Ledger information successfully retrieved.',
                'ledger_info': ledger_info,
            }

            # Cache the response for subsequent requests (e.g., 1 minute)
            cache.set(cache_key, response_data, CACHE_TIMEOUT)

            return JsonResponse(response_data)
        else:
            logger.error(f"Failed to retrieve ledger info: {response.result}")
            return JsonResponse({
                'status': 'failure',
                'message': 'Error retrieving ledger info.',
                'error_details': response.result,
            }, status=400)
    except Exception as e:
        # Handle any unexpected errors
        logger.error(f"Error fetching ledger info: {e}")
        return JsonResponse({
            'status': 'failure',
            'message': f"Error fetching ledger info: {e}"
        }, status=500)

@api_view(['GET'])
def get_xrp_reserves(request):
    """
    Fetches the XRP reserve requirements for an account:
    1. Base reserve (the amount of XRP needed to create an account).
    2. Owner reserve (the additional reserve required for each object owned by the account).
    """
    function_name = 'get_xrp_reserves'
    logger.info(f"Entering: {function_name}")

    try:
        # Get account address from the request
        wallet_address = request.GET.get('account')
        if not wallet_address:
            return JsonResponse({
                'status': 'failure',
                'message': 'Account address is required.'
            }, status=400)

        # Check if the result is cached
        cached_reserves = cache.get(wallet_address)
        if cached_reserves:
            logger.info(f"Returning cached reserves for {wallet_address}")
            return JsonResponse(cached_reserves)

        # Send the request to XRPL to get server info
        client = JsonRpcClient(JSON_RPC_URL)
        server_info_request = ServerInfo()
        server_info_response = client.request(server_info_request)

        # Check if the response was successful
        if server_info_response.is_successful():
            # Extract the reserve base and reserve increment values
            reserve_base = server_info_response.result['info']['validated_ledger']['reserve_base_xrp']
            reserve_inc = server_info_response.result['info']['validated_ledger']['reserve_inc_xrp']

            if reserve_base is not None and reserve_inc is not None:
                logger.info(f"Successfully fetched XRP reserve information for {wallet_address}.")

                # Prepare the response data
                response_data = {
                    'status': 'success',
                    'message': 'XRP reserves fetched successfully.',
                    'base_reserve': reserve_base,
                    'owner_reserve': reserve_inc,
                }

                # Cache the response for 1 minute
                cache.set(wallet_address, response_data, CACHE_TIMEOUT)
                return JsonResponse(response_data)
            else:
                # Handle missing reserve info
                logger.error(f"Reserve info not found in server response: {server_info_response.result}")
                return JsonResponse({
                    'status': 'failure',
                    'message': 'Error fetching reserve information. Reserves not found.',
                }, status=500)
        else:
            # Log the failure if the server info request was not successful
            logger.error(f"Failed to fetch server info: {server_info_response.result}")
            return JsonResponse({
                'status': 'failure',
                'message': 'Error fetching server information.',
                'error_details': server_info_response.result,
            }, status=400)
    except Exception as e:
        # Catch unexpected errors and log them
        logger.error(f"Error fetching XRP reserves for account {wallet_address}: {e}")
        return JsonResponse({
            'status': 'failure',
            'message': f"Error fetching XRP reserves: {e}"
        }, status=500)

@api_view(['GET'])
def get_account_trust_lines(request):
    """
    Fetches all trust lines associated with the given XRP account address.
    Trust lines represent relationships between accounts for non-XRP assets.
    This function caches the trust lines for faster future responses.
    """
    function_name = 'get_account_trust_lines'
    logger.info(f"Entering: {function_name}")

    try:
        # Get account address from the request
        wallet_address = request.GET.get('account')
        if not wallet_address:
            return JsonResponse({
                'status': 'failure',
                'message': 'Account address is required.'
            }, status=400)

        # Check cache for previously fetched trust lines
        cache_key = f"trust_lines_{wallet_address}"
        cached_trust_lines = cache.get(cache_key)

        if cached_trust_lines:
            logger.info(f"Returning cached trust lines for account {wallet_address}.")
            return JsonResponse({
                'status': 'success',
                'message': 'Trust lines fetched from cache.',
                'trust_lines': cached_trust_lines
            })

        # Prepare the AccountLines request to get trust lines
        account_lines_request = AccountLines(account=wallet_address)

        # Send the request to XRPL
        client = JsonRpcClient(JSON_RPC_URL)
        response = client.request(account_lines_request)

        # Check if the response is successful
        if response.is_successful():
            # Extract trust lines from the response
            trust_lines = response.result.get("lines", [])

            # Cache the response for future requests
            cache.set(cache_key, trust_lines, timeout=CACHE_TIMEOUT_FOR_TRUST_LINES)

            logger.info(f"Successfully fetched trust lines for account {wallet_address}.")

            return JsonResponse({
                'status': 'success',
                'message': 'Trust lines fetched successfully.',
                'trust_lines': trust_lines
            })

        else:
            # Log the failure if the request was not successful
            logger.error(f"Failed to fetch trust lines for account {wallet_address}: {response.result}")
            return JsonResponse({
                'status': 'failure',
                'message': 'Error fetching trust lines.',
                'error_details': response.result
            }, status=400)

    except Exception as e:
        # Catch unexpected errors and log them
        logger.error(f"Error fetching trust lines for account {wallet_address}: {e}")
        return JsonResponse({
            'status': 'failure',
            'message': f"Error fetching trust lines: {e}"
        }, status=500)

@api_view(['GET'])
def get_account_offers(request):
    """
    Fetches all offers created by the given XRP account address.
    Offers represent a proposal to buy or sell an asset on the XRP Ledger.
    """
    function_name = 'get_account_offers'
    logger.info(f"Entering: {function_name}")

    try:
        # Get account address from the request
        wallet_address = request.GET.get('account')
        if not wallet_address:
            return JsonResponse({
                'status': 'failure',
                'message': 'Account address is required.'
            }, status=400)

        # Check cache for previously fetched offers
        cache_key = f"account_offers_{wallet_address}"
        cached_offers = cache.get(cache_key)

        if cached_offers:
            logger.info(f"Returning cached offers for account {wallet_address}.")
            return JsonResponse({
                'status': 'success',
                'message': 'Offers fetched from cache.',
                'offers': cached_offers
            })

        # Prepare the AccountOffers request to get offers
        account_offers_request = AccountOffers(account=wallet_address)

        # Send the request to XRPL
        client = JsonRpcClient(JSON_RPC_URL)
        response = client.request(account_offers_request)

        # Check if the response is successful
        if response.is_successful():
            # Extract offers from the response
            offers = response.result.get("offers", [])

            # Cache the response for future requests
            cache.set(cache_key, offers, timeout=CACHE_TIMEOUT_FOR_GET_OFFERS)

            logger.info(f"Successfully fetched offers for account {wallet_address}.")
            return JsonResponse({
                'status': 'success',
                'message': 'Offers fetched successfully.',
                'offers': offers
            })
        else:
            # Log the failure if the request was not successful
            logger.error(f"Failed to fetch offers for account {wallet_address}: {response.result}")
            return JsonResponse({
                'status': 'failure',
                'message': 'Error fetching offers.',
                'error_details': response.result
            }, status=400)

    except Exception as e:
        # Catch unexpected errors and log them
        logger.error(f"Error fetching offers for account {wallet_address}: {e}")
        return JsonResponse({
            'status': 'failure',
            'message': f"Error fetching offers: {e}"
        }, status=500)

@api_view(['GET'])
def get_server_info(request):
    """
    Fetches information about the XRPL server such as the server version,
    connected peers, and other related details.
    Caches the server info to avoid redundant requests to the server.
    """
    function_name = 'get_server_info'
    logger.info(f"Entering: {function_name}")

    try:
        # Check cache for server information
        cached_server_info = cache.get('server_info')

        if cached_server_info:
            logger.info("Returning cached server information.")
            return JsonResponse({
                'status': 'success',
                'message': 'Server info fetched from cache.',
                'server_info': cached_server_info
            })

        # Prepare the ServerInfo request to get server details
        server_info_request = ServerInfo()

        # Send the request to XRPL
        client = JsonRpcClient(JSON_RPC_URL)
        response = client.request(server_info_request)

        # Check if the response is successful
        if response.is_successful():
            # Extract server information from the response
            server_info = response.result

            # Cache the server information for future requests
            cache.set('server_info', server_info, timeout=CACHE_TIMEOUT_FOR_SERVER_INFO)

            logger.info("Successfully fetched server information.")
            return JsonResponse({
                'status': 'success',
                'message': 'Server info fetched successfully.',
                'server_info': server_info
            })
        else:
            # Log the failure if the request was not successful
            logger.error(f"Failed to fetch server info: {response.result}")
            return JsonResponse({
                'status': 'failure',
                'message': 'Error fetching server information.',
                'error_details': response.result
            }, status=400)
    except Exception as e:
        # Catch unexpected errors and log them
        logger.error(f"Error fetching server information: {e}")
        return JsonResponse({
            'status': 'failure',
            'message': f"Error fetching server info: {e}"
        }, status=500)

@api_view(['GET'])
def get_trust_line(request):
    """
    Fetches trust line details for a given XRPL account.
    """
    function_name = 'get_trust_line'
    logger.info(f"Entering: {function_name}")

    wallet_address = request.GET.get('wallet_address')
    if not wallet_address:
        return JsonResponse({
            'status': 'failure',
            'message': 'wallet_address parameter is required.'
        }, status=400)

    # Check if the trust line information is already cached
    cached_trust_lines = cache.get(f'trust_lines_{wallet_address}')
    if cached_trust_lines:
        logger.info(f"Returning cached trust lines for account {wallet_address}.")
        return JsonResponse({
            'status': 'success',
            'message': 'Trust lines fetched from cache.',
            'trust_lines': cached_trust_lines
        })

    try:
        # Prepare the AccountLines request to get the trust lines for the given account
        account_lines_request = AccountLines(account=wallet_address)

        # Send the request to XRPL
        client = JsonRpcClient(JSON_RPC_URL)
        response = client.request(account_lines_request)

        # Check if the response is successful
        if response.is_successful():
            # Extract the trust lines from the response
            trust_lines = response.result.get('lines', [])

            # Cache the trust line information for future requests
            cache.set(f'trust_lines_{wallet_address}', trust_lines, timeout=CACHE_TIMEOUT)

            logger.info(f"Successfully fetched trust lines for account {wallet_address}.")
            return JsonResponse({
                'status': 'success',
                'message': 'Trust lines fetched successfully.',
                'trust_lines': trust_lines
            })
        else:
            # Log the failure if the request was not successful
            logger.error(f"Failed to fetch trust lines for account {wallet_address}: {response.result}")
            return JsonResponse({
                'status': 'failure',
                'message': 'Error fetching trust lines.',
                'error_details': response.result
            }, status=400)
    except Exception as e:
        # Catch unexpected errors and log them
        logger.error(f"Error fetching trust lines for account {wallet_address}: {e}")
        return JsonResponse({
            'status': 'failure',
            'message': f"Error fetching trust lines: {e}"
        }, status=500)

@api_view(['POST'])
def set_trust_line(request):
    function_name = 'set_trust_line'
    logger.info(f"Entering: {function_name}")

    try:
        # Extract parameters from the request
        sender_seed = request.data.get('sender_seed')
        account = request.data.get('account')  # Account to set the trust line for
        currency = request.data.get('currency')  # Currency for trust line (e.g., 'USD')
        limit = request.data.get('limit')  # Trust line limit

        # Validate required parameters
        if not sender_seed or not account or not currency or not limit:
            return JsonResponse({'status': 'failure', 'message': 'Missing required parameters'}, status=400)

        # Convert limit to drops if necessary (for XRP, it needs to be in drops)
        limit_drops = xrpl.utils.xrp_to_drops(limit) if currency == "XRP" else limit

        # Create the TrustSet transaction
        trust_set_tx = TrustSet(
            account=account,
            limit_amount={'currency': currency, 'value': str(limit_drops), 'issuer': account},
        )
        check_for_none(trust_set_tx, function_name, "Error creating TrustSet.")

        # Get the XRPL client
        client = get_xrpl_client()
        check_for_none(client, function_name, "Error client initialization failed.")

        # Sign the transaction
        sender_wallet = Wallet.from_seed(sender_seed)
        signed_tx = xrpl.transaction.sign_transaction(trust_set_tx, sender_wallet)

        # Submit the transaction
        response = client.submit(signed_tx)
        check_for_none(response, function_name, "Error submitting TrustSet transaction.")

        # Check if the transaction was successful
        if response.is_successful():
            logger.info(f"Trust line set successfully for account {account}")
            return JsonResponse({
                'status': 'success',
                'message': 'Trust line set successfully.',
                'transaction_hash': response.result['hash'],
                'account': account,
                'currency': currency,
                'limit': limit,
            })
        else:
            return JsonResponse({'status': 'failure', 'message': 'Error setting trust line.'}, status=500)

    except Exception as e:
        return JsonResponse({'status': 'failure', 'message': f"Error setting trust line: {str(e)}"}, status=500)

# Utility function to build flags
def build_flags(require_destination_tag, disable_master_key, enable_regular_key):
    flags = 0
    if require_destination_tag:
        flags |= REQUIRE_DESTINATION_TAG_FLAG
    if disable_master_key:
        flags |= DISABLE_MASTER_KEY_FLAG
    if enable_regular_key:
        flags |= ENABLE_REGULAR_KEY_FLAG
    return flags
