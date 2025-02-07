import xrpl
import json
import logging

from django.core.paginator import Paginator
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from django.http import JsonResponse
from xrpl.models import AccountTx, Tx, AccountDelete, Payment
from xrpl.wallet import generate_faucet_wallet
from xrpl.core import addresscodec
from xrpl.utils import xrp_to_drops, drops_to_xrp
from xrpl.wallet import Wallet
from xrpl.models.requests import AccountInfo

from .db_operations import save_account_data_to_databases
from .models import XrplAccountData, XrplPaymentData
from xrpl.transaction import submit_and_wait
from xrpl.models.transactions import AccountSet
from decimal import Decimal
from .utils import validate_account_id, get_xrpl_client, handle_error, get_account_reserves

logger = logging.getLogger('xrpl_app')

FAUCET_URL = "https://faucet.altnet.rippletest.net/accounts"

class AccountInfoPagination(PageNumberPagination):
    page_size = 10

def create_account(request):
    function_name = 'create_account'
    logger.info(f"Entering: {function_name}")

    try:
        client = get_xrpl_client()

        if not client:
            return handle_error({'status': 'failure', 'message': f"Error client initialization failed."}, status_code=500, function_name=function_name)

        new_wallet = generate_faucet_wallet(client, debug=True)

        if not new_wallet:
            return handle_error({'status': 'failure', 'message': f"Error creating new wallet. Wallet is empty"}, status_code=500, function_name=function_name)

        test_account = new_wallet.address
        test_xaddress = addresscodec.classic_address_to_xaddress(test_account, tag=12345, is_test_network=True)
        logger.debug(f"Classic address: " + test_account)
        logger.debug(f"X-address: " + test_xaddress)

        acct_info = AccountInfo(
            account=test_account,
            ledger_index="validated",
            strict=True,
        )

        if not acct_info:
            return handle_error({'status': 'failure', 'message': f"Error creating Account Info."}, status_code=500, function_name=function_name)

        response = client.request(acct_info)
        logger.info("response.status: " + response.status)

        if response and response.status == 'success':
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
    except Exception as e:
        return handle_error({'status': 'failure', 'message': f"Error creating new wallet: {e}"}, status_code=500, function_name=function_name)

def get_wallet_info(request, wallet_address):
    function_name = 'get_wallet_info'
    logger.info(f"Entering: {function_name}")

    try:
        # Validate the account ID format
        if not validate_account_id(wallet_address):
            return handle_error({'status': 'failure', 'message': 'Invalid address format.'}, status_code=400, function_name=function_name)

        # Log the account ID being queried
        logger.info(f"Fetching account info for: {wallet_address}")

        # Connect to the XRPL Testnet
        client = get_xrpl_client()

        if not client:
            return handle_error({'status': 'failure', 'message': f"Error client initialization failed."}, status_code=500,
                                function_name=function_name)

        # Create an AccountInfo request
        account_info_request = AccountInfo(account=wallet_address, ledger_index="validated")

        # Send the request to the XRPL
        response = client.request(account_info_request)
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
    except Exception as e:
        return handle_error({'status': 'failure', 'message': f"Error fetching account info: {e}"}, status_code=500, function_name=function_name)

def check_wallet_balance(request, wallet_address):
    function_name = 'check_wallet_balance'
    logger.info(f"Entering: {function_name}")

    # Log the start of the check balance request
    logger.info(f"Request received to check balance for address: {wallet_address}")

    try:
        # Validate the address format
        if not validate_account_id(wallet_address):
            return handle_error({'status': 'failure', 'message': 'Invalid address format.'}, status_code=400, function_name=function_name)

        # Get the XRPL client
        client = get_xrpl_client()

        if not client:
            return handle_error({'status': 'failure', 'message': f"Error client initialization failed."}, status_code=500,
                                function_name=function_name)

        # Create an AccountInfo request
        account_info = AccountInfo(account=wallet_address)

        # Send the request to the XRPL client
        logger.info(f"Sending account info request for address: {wallet_address}")
        response = client.request(account_info)

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

    except Exception as e:
        # Log any unexpected errors that occur
        return handle_error({'status': 'failure', 'message': f"Error fetching account info: {e}"}, status_code=500, function_name=function_name)

def account_set(request):
    function_name = 'account_set'
    logger.info(f"Entering: {function_name}")

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

        if not client:
            return handle_error({'status': 'failure', 'message': f"Error client initialization failed."}, status_code=500,
                                function_name=function_name)

        # Submit the transaction
        response = submit_and_wait(account_set_tx, client, sender_wallet)

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
    except Exception as e:
        return handle_error({'status': 'failure', 'message': f"Error fetching account info: {e}"}, status_code=500, function_name=function_name)

def get_transaction_history(request, wallet_address):
    function_name = 'get_transaction_history'
    logger.info(f"Entering: {function_name}")

    if not validate_account_id(wallet_address):
        return handle_error({'status': 'failure', 'message': 'Invalid address format.'}, status_code=400, function_name=function_name)

    try:
        client = get_xrpl_client()

        if not client:
            return handle_error({'status': 'failure', 'message': f"Error client initialization failed."}, status_code=500,
                                function_name=function_name)

        # Create an AccountTx request
        account_tx_request = AccountTx(account=wallet_address)

        # Submit the request to the XRPL
        response = client.request(account_tx_request)

        # Log the response
        logger.info(f"Transaction history fetched for address: {wallet_address}")

        # Return the transaction history
        # return JsonResponse(response.result)
        return JsonResponse({
            'status': 'success',
            'message': 'Transaction history successfully retrieved.',
            'response': response.result,
        })
    except Exception as e:
        return handle_error({'status': 'failure', 'message': f"Error fetching transaction history info: {e}"}, status_code=500, function_name=function_name)

@api_view(['GET'])
def get_transaction_history_with_pagination(request, wallet_address):
    function_name = 'get_transaction_history_with_pagination'
    logger.info(f"Entering: {function_name}")

    if not validate_account_id(wallet_address):
        return handle_error({'status': 'failure', 'message': 'Invalid address format.'}, status_code=400, function_name=function_name)

    try:
        client = get_xrpl_client()

        if not client:
            return handle_error({'status': 'failure', 'message': f"Error client initialization failed."}, status_code=500,
                                function_name=function_name)

        transactions = []
        marker = None

        while True:
            account_tx_request = AccountTx(
                account=wallet_address,
                ledger_index_min=-1,
                ledger_index_max=-1,
                limit=100,
                marker=marker,
            )
            response = client.request(account_tx_request)
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
    except Exception as e:
        return handle_error({'status': 'failure', 'message': f"Error fetching transaction history info: {e}"}, status_code=500, function_name=function_name)

def check_transaction_status(request, tx_hash):
    function_name = 'check_transaction_status'
    logger.info(f"Entering: {function_name}")

    try:
        # Log the start of the transaction status check
        logger.info(f"Checking transaction status for hash: {tx_hash}")

        # Get the XRPL client
        client = get_xrpl_client()

        if not client:
            return handle_error({'status': 'failure', 'message': f"Error client initialization failed."}, status_code=500,
                                function_name=function_name)


        # Create a transaction request
        tx_request  = Tx(transaction=tx_hash)

        # Send the request to the XRPL
        response = client.request(tx_request )

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

    except Exception as e:
        # Log any unexpected errors
        return handle_error({'status': 'failure', 'message': f"Error while checking transaction status for hash {tx_hash}: {e}"}, status_code=500, function_name=function_name)

def send_payment(request):
    function_name = 'send_payment'
    logger.info(f"Entering: {function_name}")

    try:
        # account = request.GET.get('sender_address')
        sender_seed = request.GET.get('sender_seed')
        receiver_address = request.GET.get('receiver')
        amount_xrp = Decimal(request.GET.get('amount'))

        amount_drops = xrp_to_drops(amount_xrp)

        client = get_xrpl_client()

        if not client:
            return handle_error({'status': 'failure', 'message': f"Error client initialization failed."}, status_code=500,
                                function_name=function_name)

        sender_wallet = Wallet.from_seed(sender_seed)
        sender_address = sender_wallet.classic_address

        # Construct the Payment transaction
        payment_transaction = Payment(
            account=sender_address,
            destination=receiver_address,
            amount=amount_drops,
        )

        # Submit the transaction
        payment_response = submit_and_wait(payment_transaction, client, sender_wallet)

        if payment_response and payment_response.is_successful():
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
    except Exception as e:
        return handle_error({'status': 'failure', 'message': f"Error sending payment: {e}"}, status_code=500, function_name=function_name)

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

    # Step 1: Check the wallet balance
    try:
        # Get the sender's seed from the request
        sender_seed = request.GET.get('sender_seed')
        if not sender_seed:
            return handle_error({'status': 'failure', 'message': 'Sender seed is required.'}, status_code=400, function_name=function_name)

        # Prepare the request to get account info
        account_info_request = AccountInfo(
            account=wallet_address,
            ledger_index="validated",  # Use the latest validated ledger
            strict=True,
        )

        # Connect to the XRPL client
        client = get_xrpl_client()

        if not client:
            return handle_error({'status': 'failure', 'message': f"Error client initialization failed."}, status_code=500,
                                function_name=function_name)

        # Send the request to XRPL
        response = client.request(account_info_request)

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

            # Sign the transaction (you need the private key for this)
            private_key = sender_seed
            signer = xrpl.wallet.Wallet(private_key, False)

            # Step 3: Submit the transaction to the XRPL
            tx_response = xrpl.transaction.sign_and_submit(account_delete_tx, client, signer)

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
    except Exception as e:
        return handle_error({'status': 'failure', 'message': f"Error attempting to delete account: {e}"}, status_code=500, function_name=function_name)
