from django.core.paginator import Paginator
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo, AccountTx
from xrpl.wallet import Wallet
from .models import XRPLAccount
from .serializers import XRPLAccountSerializer
import xrpl
from django.http import JsonResponse, HttpResponseBadRequest
from xrpl.models import AccountTx, Tx
from xrpl.utils import xrp_to_drops
from xrpl.wallet import Wallet
from xrpl.models.requests import AccountInfo
from .models import XRPLAccount
# from .utils.error_handling import validate_account_id
# from .utils.error_handling import handle_error
# from .utils.xrpl_client import get_xrpl_client
from xrpl.transaction import submit_and_wait
from xrpl.models.transactions import AccountSet
from decimal import Decimal
from .models import Payment
import json
import requests
import logging
import time

logger = logging.getLogger(__name__)

JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/"
FAUCET_URL = "https://faucet.altnet.rippletest.net/accounts"

class XRPLAccountView(APIView):
    def get(self, request, account_id):
        client = JsonRpcClient("https://s.altnet.rippletest.net:51234")  # Testnet URL
        account_info = AccountInfo(account=account_id)
        response = client.request(account_info)

        if response.is_successful():
            balance = response.result.get("account_data", {}).get("Balance", "0")
            account, created = XRPLAccount.objects.get_or_create(
                account_id=account_id,
                defaults={'balance': balance}
            )
            # serializer = XRPLAccountSerializer(account)
            # return Response(serializer.data, status=status.HTTP_200_OK)

            # Return the full response from the XRPL
            return Response(response.result, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND)

class XRPLAccountTransactionsView(APIView):
    def get(self, request, account_id):
        client = JsonRpcClient("https://s.altnet.rippletest.net:51234")  # Testnet URL
        account_tx = AccountTx(account=account_id)
        response = client.request(account_tx)

        if response.is_successful():
            transactions = response.result.get("transactions", [])
            return Response(transactions, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Unable to fetch transactions"}, status=status.HTTP_404_NOT_FOUND)

class XRPLCreateAccountView(APIView):
    def post(self, request):
        # Generate a new wallet (account)
        wallet = Wallet.create()

        # Fund the account with Testnet faucet (optional)
        client = JsonRpcClient("https://s.altnet.rippletest.net:51234")  # Testnet URL
        response = client.request({
            "command": "faucet",
            "destination": wallet.classic_address,
        })

        if response.is_successful():
            return Response({
                "address": wallet.classic_address,
                "secret": wallet.seed,  # Be cautious with exposing the secret
                "message": "Account created and funded successfully."
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({"error": "Failed to fund account with Testnet faucet."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AccountInfoPagination(PageNumberPagination):
    page_size = 10

def create_account(request):
    try:
        # Create a new wallet on the XRPL Testnet
        client = get_xrpl_client()
        wallet = Wallet.create()
        account_id = wallet.classic_address
        balance = 0  # New accounts start with 0 balance on testnet

        # Save account to the database
        xrpl_account = XRPLAccount(account_id=account_id, secret=wallet.seed, balance=balance)
        xrpl_account.save()

        logger.info(f"Account created: {account_id}")

        # Use the XRPL Testnet Faucet to fund the account
        faucet_response = requests.post(FAUCET_URL, json={"destination": account_id})
        if faucet_response.status_code == 200:
            faucet_data = faucet_response.json()
            pretty_faucet_data = json.dumps(faucet_data, indent=4)
            logger.info(f"Account funded via faucet:\n{pretty_faucet_data}")
        else:
            logger.error(f"Failed to fund account via faucet: {faucet_response.text}")
            return handle_error('Failed to fund account via faucet', status_code=500)

        # Retry fetching account info until it succeeds
        max_retries = 5
        retry_delay = 5  # seconds
        for attempt in range(max_retries):
            time.sleep(retry_delay)  # Wait before retrying
            account_info_request = AccountInfo(account=account_id, ledger_index="validated")
            response = client.request(account_info_request)

            if response.is_successful():
                logger.info(f"Response data: {response.result}")

                balance = int(response.result['account_data']['Balance']) / 1_000_000  # Convert drops to XRP
                xrpl_account.balance = balance
                xrpl_account.transaction_hash = response.result['account_data']['PreviousTxnID']
                xrpl_account.save()

                logger.info(f"Account balance updated: {balance} XRP")

                return JsonResponse({
                    'account_id': account_id,
                    'secret': wallet.seed,
                    'balance': balance,
                    'transaction_hash':xrpl_account.transaction_hash,
                })
            else:
                logger.warning(f"Attempt {attempt + 1}: Account not found yet. Retrying...")

        # If all retries fail
        return handle_error('Account not found after multiple attempts', status_code=500)
    except Exception as e:
        return handle_error(f"Error creating account: {e}")

def get_account_info(request, account_id):
    try:
        # Validate the account ID format
        if not account_id.startswith("r") or len(account_id) < 25 or len(account_id) > 35:
            logger.error(f"Invalid account ID format: {account_id}")
            return JsonResponse({'error': 'Invalid account ID format'}, status=400)

        # Log the account ID being queried
        logger.info(f"Fetching account info for: {account_id}")

        # Connect to the XRPL Testnet
        client = get_xrpl_client()

        # Create an AccountInfo request
        account_info_request = AccountInfo(account=account_id, ledger_index="validated")

        # Send the request to the XRPL
        response = client.request(account_info_request)

        # Log the raw response for debugging
        logger.info(f"Raw XRPL response: {response}")

        # Check if the request was successful
        if response.is_successful():
            balance = response.result['account_data']['Balance']
            logger.info(f"Account found: {account_id}, Balance: {balance}")
            return JsonResponse({
                'account_id': account_id,
                'balance': balance,
            })
        else:
            return handle_error('Account not found on XRPL', status_code=404)
    except Exception as e:
        return handle_error(f"Error fetching account info: {e}")

def check_balance(request, address):
    # Log the start of the check balance request
    logger.info(f"Request received to check balance for address: {address}")

    try:
        # Validate the address format
        if not address or not address.startswith('r') or len(address) < 25 or len(address) > 35:
            logger.error(f"Invalid address format: {address}")
            return JsonResponse({"error": "Invalid address format"}, status=400)

        # Get the XRPL client
        client = get_xrpl_client()

        # Create an AccountInfo request
        account_info = AccountInfo(account=address)

        # Send the request to the XRPL client
        logger.info(f"Sending account info request for address: {address}")
        response = client.request(account_info)

        # Check if the request was successful
        if response.is_successful():
            # Extract the balance in drops and convert to XRP
            balance_in_drops = int(response.result["account_data"]["Balance"])
            balance_in_xrp = balance_in_drops / 1_000_000  # Convert drops to XRP

            # Log the successful balance retrieval
            logger.info(f"Balance for address {address} retrieved successfully: {balance_in_xrp} XRP")

            # Return the balance as JSON response
            return JsonResponse({"balance": balance_in_xrp})
        else:
            # Log the failure to fetch account info
            return handle_error('Account not found on XRPL', status_code=404)

    except Exception as e:
        # Log any unexpected errors that occur
        return handle_error(f"Error fetching account info: {e}")

def account_set(request):
    try:
        sender_seed = request.GET.get('sender_seed')
        require_destination_tag = request.GET.get('require_destination_tag', 'false').lower() == 'true'
        disable_master_key = request.GET.get('disable_master_key', 'false').lower() == 'true'
        enable_regular_key = request.GET.get('enable_regular_key', 'false').lower() == 'true'

        # Log the passed in account setting values
        logger.info(f"require_destination_tag value set to: {require_destination_tag}")
        logger.info(f"disable_master_key value set to: {disable_master_key}")
        logger.info(f"enable_regular_key value set to: {enable_regular_key}")

        # Create the wallet from the sender seed
        sender_wallet = Wallet.from_seed(sender_seed)
        sender_address = sender_wallet.classic_address

        # Build the flags you want to set
        flags = 0

        # Enable or disable the requireDestinationTag flag
        if require_destination_tag:
            flags |= 0x00010000  # 0x00010000: Require Destination Tag

        # Disable master key
        if disable_master_key:
            flags |= 0x00040000  # 0x00040000: Disable Master Key

        # Enable regular key
        if enable_regular_key:
            flags |= 0x00080000  # 0x00080000: Enable Regular Key

        # Create the AccountSet transaction
        account_set_tx = AccountSet(
            account=sender_address,
            flags=flags
        )

        # Get the client to communicate with XRPL
        client = get_xrpl_client()

        # Submit the transaction
        response = submit_and_wait(account_set_tx, client, sender_wallet)

        # Check if the transaction was successful
        if response.is_successful():
            logger.info(f"AccountSet transaction successful for account {sender_address}")
            return JsonResponse({
                'status': 'success',
                'transaction_hash': response.result['hash'],
                'account': sender_address,
                'settings': response.result
            })

        else:
            return handle_error(f"AccountSet transaction failed for account {sender_address}. Response: {response}", status_code=404)
    except Exception as e:
        return handle_error(f"Error fetching account info: {e}")

def get_transaction_history(request, address):
    if not validate_account_id(address):
        return handle_error('Invalid address provided', status_code=400)

    try:
        client = get_xrpl_client()

        # Create an AccountTx request
        account_tx_request = AccountTx(account=address)

        # Submit the request to the XRPL
        response = client.request(account_tx_request)

        # Log the response
        logger.info(f"Transaction history fetched for address: {address}")

        # Return the transaction history
        return JsonResponse(response.result)
    except Exception as e:
        return handle_error(f"Unexpected error: {e}")

@api_view(['POST'])
def get_transaction_history_with_pagination(request, address):
    if not validate_account_id(address):
        return handle_error('Invalid address provided', status_code=400)

    try:
        client = get_xrpl_client()
        transactions = []
        marker = None

        while True:
            account_tx_request = AccountTx(
                account=address,
                ledger_index_min=-1,
                ledger_index_max=-1,
                limit=100,
                marker=marker,
            )
            response = client.request(account_tx_request)
            transactions.extend(response.result["transactions"])

            # Check if there are more transactions to fetch
            marker = response.result.get("marker")
            if not marker:
                break

        # Get pagination parameters from request
        page = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 10)

        paginator = Paginator(transactions, page_size)
        paginated_transactions = paginator.get_page(page)

        data = {
            "transactions": list(paginated_transactions),
            "total_transactions": paginator.count,
            "pages": paginator.num_pages,
            "current_page": paginated_transactions.number,
        }

        logger.info(f"Transaction history fetched for address: {address}")
        return JsonResponse(data)
    except Exception as e:
        return handle_error(f"Unexpected error: {e}")

def check_transaction_status(request, tx_hash):
    try:
        # Log the start of the transaction status check
        logger.info(f"Checking transaction status for hash: {tx_hash}")

        # Get the XRPL client
        client = get_xrpl_client()

        # Create a transaction request
        tx_request  = Tx(transaction=tx_hash)

        # Send the request to the XRPL
        response = client.request(tx_request )

        # Log the raw response for debugging
        logger.debug(f"Raw XRPL response for transaction {tx_hash}: {response}")

        # Check if the request was successful
        if response.is_successful():
            # Log the successful retrieval of transaction status
            logger.info(f"Transaction status retrieved successfully for hash: {tx_hash}")
            return JsonResponse(response.result)
        else:
            # Log the failure to retrieve transaction status
            return handle_error("Failed to retrieve transaction status", status_code=500)
    except Exception as e:
        # Log any unexpected errors
        return handle_error(f"Unexpected error while checking transaction status for hash {tx_hash}: {e}")

def send_payment(request):
    try:
        # account = request.GET.get('sender_address')
        sender_seed = request.GET.get('sender_seed')
        receiver_address = request.GET.get('receiver')
        amount_xrp = Decimal(request.GET.get('amount'))

        amount_drops = xrp_to_drops(amount_xrp)

        client = get_xrpl_client()
        sender_wallet = Wallet.from_seed(sender_seed)
        sender_address = sender_wallet.classic_address

        # Construct the Payment transaction
        payment_transaction = xrpl.models.transactions.Payment(
            account=sender_address,
            destination=receiver_address,
            amount=amount_drops,
        )

        # Submit the transaction
        payment_response = submit_and_wait(payment_transaction, client, sender_wallet)

        if payment_response.is_successful():
            transaction_hash = payment_response.result['hash']
            logger.info(f"Payment successful: {transaction_hash}")

            # Save the payment details (assuming you have a Payment model)
            payment = Payment(
                sender=sender_address,
                receiver=receiver_address,
                amount=amount_xrp,
                transaction_hash=transaction_hash,
            )
            payment.save()

            # Update sender and receiver balances (assuming you have an XRPLAccount model)
            sender_account = XRPLAccount.objects.get(account_id=sender_address)
            sender_account.balance -= amount_xrp
            sender_account.save()

            receiver_account, created = XRPLAccount.objects.get_or_create(
                account_id=receiver_address,
                defaults={'balance': amount_xrp}
            )
            if not created:
                receiver_account.balance += amount_xrp
                receiver_account.save()

            return JsonResponse({
                'status': 'success',
                'transaction_hash': transaction_hash,
                'sender': sender_address,
                'receiver': receiver_address,
                'amount': amount_xrp,
            })
        else:
            return handle_error('Payment failed', status_code=500)
    except Exception as e:
        return handle_error(f"Error sending payment: {e}")

def handle_error(error_message, status_code=500):
    """
    Logs an error and returns a JsonResponse with the error message.
    """
    logger.error(error_message)
    return JsonResponse({'error': error_message}, status=status_code)

def validate_account_id(account_id):
    """
    Validates the format of an XRPL account ID.
    """
    if not account_id.startswith("r") or len(account_id) < 25 or len(account_id) > 35:
        return False
    return True

def get_xrpl_client():
    """
    Returns a configured JSON-RPC client for the XRPL Testnet.
    """
    return JsonRpcClient(JSON_RPC_URL)