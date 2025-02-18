import json
from decimal import Decimal

from django.http import JsonResponse
from xrpl.models import ServerInfo, AccountDelete, AccountInfo, AccountTx, AccountSet, AccountObjects, SetRegularKey, \
    AccountOffers, AccountLines
import logging

from django.db import transaction

from ..constants import XRPL_RESPONSE
from ..errors.error_handling import handle_engine_result
from ..models import XrplAccountData
from ..utils import get_xrpl_client

logger = logging.getLogger('xrpl_app')


def get_account_objects(account: str):
    # Query Account Objects
    account_objects_request = AccountObjects(account=account)
    account_objects_response = get_xrpl_client().request(account_objects_request)

    if "error" in account_objects_response.result:
        logger.error(f"Account {account} not found!")
        return None

    return account_objects_response.result.get('account_objects', [])


def check_check_entries(account_objects):
    # Filter check entries
    check_entries = [entry for entry in account_objects if entry.get('LedgerEntryType') == 'Check']

    if check_entries:
        logger.error(f"Check entries found: {json.dumps(check_entries, indent=2)}")
        return False

    logger.info("No Check entries found.")
    return True


def get_account_reserves():
    """
    Fetches the current reserve requirements from the XRP Ledger.

    This function queries the XRP Ledger ledger to retrieve the base reserve
    and reserve increment values, which are required for account operations.
    It handles errors gracefully and logs appropriate messages for debugging.

    Returns:
        tuple: A tuple containing (base_reserve, reserve_inc) as integers.
               If the data is unavailable or an error occurs, returns (None, None).

    Example:
        base_reserve, reserve_inc = get_account_reserves()
        if base_reserve and reserve_inc:
            print(f"Base Reserve: {base_reserve}, Reserve Increment: {reserve_inc}")
    """
    try:
        # Request ledger info from the XRP Ledger using the XRPL client
        response = get_xrpl_client().request(ServerInfo())

        # Extract the 'validated_ledger' object from the ledger info response
        validated_ledger = response.result.get('info', {}).get('validated_ledger', {})

        # Retrieve the base reserve and reserve increment values from the validated ledger
        base_reserve = validated_ledger.get('reserve_base_xrp')
        reserve_inc = validated_ledger.get('reserve_inc_xrp')

        # Check if either value is missing (None)
        if base_reserve is None or reserve_inc is None:
            logger.error("Reserve data not found in ledger info.")
            return None, None

        # Convert the values to integers and return them
        return int(base_reserve), int(reserve_inc)

    except Exception as e:
        # Log any exceptions that occur during the process
        logger.error(f"Error fetching ledger info: {e}")
        return None, None


def update_sender_account_balances(sender_address: str, amount_xrp: Decimal):
    try:
        with transaction.atomic():  # Ensures the update is committed
            sender_account = XrplAccountData.objects.select_for_update().get(account=sender_address)

            if amount_xrp <= 0:
                logger.warning(f"Skipping update: amount_xrp={amount_xrp}")
                return

            sender_account.balance -= amount_xrp
            sender_account.save(update_fields=["balance"])  # Force update

    except XrplAccountData.DoesNotExist:
        logger.error(f"Sender account {sender_address} not found.")
        raise ValueError("Sender account does not exist.")
    except Exception as e:
        logger.error(f"Unexpected error updating account balances: {str(e)}", exc_info=True)
        raise ValueError("An unexpected error occurred while updating balances.") from e


def update_receiver_account_balances(receiver_address: str, amount_xrp: Decimal):
    try:
        with transaction.atomic():  # Ensures the update is committed
            # Fetch or create receiver's account and update balance
            receiver_account = XrplAccountData.objects.get(account=receiver_address)

            if amount_xrp <= 0:
                logger.warning(f"Skipping update: amount_xrp={amount_xrp}")
                return

            receiver_account.balance += amount_xrp
            receiver_account.save()

    except XrplAccountData.DoesNotExist:
        logger.error(f"Sender account {receiver_address} not found.")
        raise ValueError("Sender account does not exist.")
    except Exception as e:
        logger.error(f"Unexpected error updating account balances: {str(e)}", exc_info=True)
        raise ValueError("An unexpected error occurred while updating balances.") from e


def get_account_details(client, wallet_address: str):
    """
    Retrieves details for a specified XRP Ledger (XRPL) wallet address using an XRPL client.

    Args:
        client: An XRPL client instance capable of making requests to the XRPL network.
        wallet_address (str): The classic address of the wallet whose details are desired.

    Returns:
        dict or None: A dictionary containing the account details if successful, or None if there was an error.

    This function prepares a request to retrieve account details for a given wallet address and sends it
    using the provided XRPL client. It logs debug information about the response and checks if the request
    was successful. If so, it returns the account details in a dictionary format. Otherwise, it logs an error
    and returns None.
    """
    try:
        # Prepare account data for the request
        account_info = prepare_account_data(wallet_address, False)

        # Send the request to the XRPL client
        response = client.request(account_info)

        # Log debug information about the response
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        print(response.is_successful())

        # Check if the response status is 'success'
        if response and response.status == 'success':
            result = response.result
            return {
                'result': result,
            }
        else:
            logger.error(f"Failed to retrieve account details. Response: {response.text}")
            # Handle the engine result
            engine_result = response.result.get("engine_result")
            if engine_result is None:
                engine_result = 'unknown'

            engine_result_message = response.result.get("engine_result_message",
                                                        "Transaction response was unsuccessful.")
            handle_engine_result(engine_result, engine_result_message)
            return None

    except Exception as e:
        # Log any exceptions that occur during the request
        logger.error(f"Error retrieving account details: {str(e)}")
        return None


def prepare_account_data(sender_address, black_hole):
    """
    Prepares an `AccountInfo` request object to fetch account data for a given sender address.

    This function creates and returns an `AccountInfo` object configured to retrieve
    the latest validated account information for the specified sender address. The
    request is set to use the latest validated ledger and enforces strict validation
    to ensure the address is in the correct format.

    Args:
        sender_address (str): The XRP Ledger address of the sender whose account data
                             is to be fetched.

    Returns:
        AccountInfo: A configured `AccountInfo` object ready to be used in a request.

    Example:
        account_info_request = prepare_account_data("rExampleAddress123")
        response = xrpl_client.request(account_info_request)
    """
    if black_hole:
        return AccountInfo(
            account=sender_address,
        )
    else:
        return AccountInfo(
            account=sender_address,
            ledger_index="validated",  # Use the latest validated ledger
            strict=True,  # Enforce strict validation of the address format
        )


def prepare_regular_key(wallet_address, black_hole_address):
    return SetRegularKey(
        account=wallet_address,
        regular_key=black_hole_address
    )


def prepare_account_delete(sender_address):
    """
    Prepares an AccountDelete transaction for the XRPL.

    Args:
        sender_address (str): The address of the account to be deleted.

    Returns:
        xrpl.models.transactions.AccountDelete: An AccountDelete transaction object with the specified parameters.

    This function constructs an AccountDelete transaction for the XRPL, which is used to delete an account.
    It takes one argument: `sender_address`, which is the address of the account that will be deleted.
    The function returns an `AccountDelete` object configured with this parameter. Note that the destination
    field in AccountDelete must match the sender's address, and a transaction fee is specified.
    """
    # Prepare and return an AccountDelete transaction object
    return AccountDelete(
        account=sender_address,
        destination=sender_address,
        fee="12",
    )


def account_reserves_response(server_information_response, reserve_base, reserve_inc):
    """
    Creates a JSON response for successfully fetching XRP reserves.

    Args:
        server_information_response (xrpl.models.response.Response): The response object from the XRPL ledger information query.
        reserve_base (int): The base reserve amount in drops.
        reserve_inc (int): The incremental reserve amount per account in drops.

    Returns:
        JsonResponse: A Django JsonResponse containing the success message and reserve details.
    """
    # Create a JSON response with success status, message, and reserve details
    return JsonResponse({
        'status': 'success',  # Indicate that the operation was successful
        'message': 'XRP reserves fetched successfully.',  # Provide a success message
        'base_reserve': reserve_base,  # Include the base reserve amount in drops
        'owner_reserve': reserve_inc,  # Include the incremental reserve amount per account in drops
        'result': server_information_response.result  # Include the result from the XRPL ledger information query
    })


def account_set_tx_response(response, sender_address):
    """
    Constructs a JSON response for an AccountSet transaction.

    Args:
        response (xrpl.models.response.Response): The response from the XRPL client containing details of the transaction.
        sender_address (str): The address of the account that sent the AccountSet transaction.

    Returns:
        JsonResponse: A Django JsonResponse object containing the result of the AccountSet transaction.

    This function prepares a JSON response for an AccountSet transaction, including the status and message of the operation.
    It takes two arguments:
    - `response`: The response from the XRPL client, which contains details about the transaction.
    - `sender_address`: The address of the account that sent the AccountSet transaction.

    The function returns a Django JsonResponse object with keys for 'status', 'message', 'transaction_hash', 'account', and 'result'.
    - 'status' indicates the outcome of the operation ('success' or an error message).
    - 'message' provides a brief description of the operation result.
    - 'transaction_hash' contains the hash of the transaction.
    - 'account' contains the address of the sender's account.
    - 'result' contains the actual response from the XRPL client regarding the transaction.

    This allows for a consistent format to inform clients about whether the AccountSet transaction was successful and provide additional details if needed.
    """
    # Log successful completion of the AccountSet transaction
    logger.info(f"AccountSet transaction successful for account {sender_address}")

    # Prepare and return a JSON response for the AccountSet transaction
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully updated account settings.',
        'transaction_hash': response['hash'],  # Corrected from 'response.result' to 'response.result["hash"]'
        'account': sender_address,
        'result': response
    })


def black_hole_xrp_response(response):
    return JsonResponse({
        'status': 'success',
        'message': 'Account successfully black holed.',
        'result': response.result,
    })


def delete_account_response(tx_response):
    """
    Constructs a JSON response for the deletion of an account.

    Args:
        tx_response (xrpl.models.transactions.TransactionResponse): The transaction response from the XRPL client.

    Returns:
        JsonResponse: A Django JsonResponse object containing the result of the account deletion.

    This function prepares a JSON response for the deletion of an account, including the status and message of the operation.
    It takes one argument:
    - `tx_response`: The transaction response from the XRPL client, which contains details about the deletion process.

    The function returns a Django JsonResponse object with keys for 'status', 'message', and 'tx_response'.
    - 'status' indicates the outcome of the operation ('success' or an error message).
    - 'message' provides a brief description of the operation result.
    - 'tx_response' contains the actual response from the XRPL client regarding the transaction.

    This allows for a consistent format to inform clients about whether the account deletion was successful and provide additional details if needed.
    """
    # Prepare and return a JSON response for the account deletion
    return JsonResponse({
        'status': 'success',
        'message': 'Account successfully black-holed.',
        'tx_response': tx_response.result,
    })


def account_tx_with_pagination_response(paginated_transactions, count, num_pages):
    """
    Constructs a response dictionary for the account transaction history with pagination information.

    Args:
        paginated_transactions (xrpl.models.transactions.AccountTx): A paginated list of transactions.
        count (int): The total number of transactions retrieved.
        num_pages (int): The total number of pages available for pagination.

    Returns:
        JsonResponse: A JsonResponse containing the response data including transactions, counts, and pagination details.

    This function prepares a response dictionary that encapsulates the results of retrieving an account's transaction history with pagination support.
    It takes three arguments:
    - `paginated_transactions`: The paginated list of transactions retrieved from the XRPL.
    - `count`: The total number of transactions available for the given account.
    - `num_pages`: The total number of pages available for pagination.

    The function returns a dictionary with keys for status, message, transactions, total_transactions, pages, and current_page,
    providing a structured format to display the transaction history along with pagination information.
    """
    # Prepare and return a response dictionary containing transaction data and pagination details
    return JsonResponse({
        "status": "success",
        "message": "Transaction history successfully retrieved.",
        "transactions": list(paginated_transactions),
        "total_transactions": count,
        "pages": num_pages,
        "current_page": paginated_transactions.number,
    })


def account_delete_tx_response(account_delete_response_result, payment_response):
    return JsonResponse({
        'status': 'success',
        'message': 'Funds transferred and account deleted successfully.',
        'account_delete_response': account_delete_response_result,
        'payment_response': payment_response,
        'payment_response_hash': payment_response['hash'],
        'account_delete_response_hash': account_delete_response_result['hash']
    })


def create_wallet_info_response(base_reserve, reserve_increment, account_details):
    """
    Creates and returns a JSON response containing wallet information including base reserve, reserve increment, and account details.

    Args:
        base_reserve (float): The base reserve amount for the wallet.
        reserve_increment (float): The incremental reserve amount for the wallet.
        account_details (dict): Detailed account information from the XRPL.

    Returns:
        JsonResponse: A JSON response object with the wallet information.
    """
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully retrieved account information.',
        'reserve': base_reserve,
        'reserve_increment': reserve_increment,
        'result': account_details,
    })


def create_wallet_balance_response(balance_in_xrp):
    """
    Creates and returns a JSON response containing the wallet balance in XRP.

    Args:
        balance_in_xrp (float): The balance of the wallet in XRP.

    Returns:
        JsonResponse: A JSON response object with the balance information.
    """
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully retrieved account balance.',
        "balance": balance_in_xrp,
    })


def create_account_response(wallet_address, seed, xrp_balance, account_details):
    """
    Creates and returns a JSON response containing details of a newly created wallet.

    Args:
        wallet_address (str): The address of the newly created wallet.
        seed (str): The secret seed for the wallet.
        xrp_balance (float): The initial XRP balance of the wallet.
        account_details (dict): Detailed account information from the XRPL.

    Returns:
        JsonResponse: A JSON response object with the wallet creation details.
    """
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully created wallet.',
        'account_id': wallet_address,
        'secret': seed,
        'balance': xrp_balance,
        'transaction_hash': account_details['result']['ledger_hash'],
        'previous_transaction_id': account_details['result']['account_data']['PreviousTxnID'],
    })


def create_account_offers_response(orderbook_info, result, acct_offers):
    return JsonResponse({
        'status': 'success',
        'message': 'Offers successfully created.',
        'result': result.result,
        'orderbook_info': orderbook_info.result,
        'acct_offers': acct_offers.result,
    })


def create_get_account_offers_response(response):
    return JsonResponse({
        'status': 'success',
        'message': 'Offers fetched successfully.',
        'result': response,
    })


def create_multiple_account_response(transactions):
    """
    Creates and returns a JSON response containing details of multiple newly created wallets.

    Args:
        transactions (list): A list of dictionaries, each representing a transaction that created a new wallet.

    Returns:
        JsonResponse: A JSON response object with the details of the created wallets.
    """
    return JsonResponse({
        "status": "success",
        "message": f"{len(transactions)} Wallets created.",
        "transactions": transactions,
    })


def create_account_delete_transaction(sender_address: str, receiver_address: str, last_ledger_sequence: str):
    """
    Creates a transaction to delete an account on the XRP Ledger.

    Args:
        sender_address (str): The address of the account that will send the transaction.
        receiver_address (str): The address of the account that will be deleted.

    Returns:
        AccountDelete: An AccountDelete object representing the created transaction.

    This function constructs a transaction to delete an account on the XRP Ledger. It takes two arguments:
    - `sender_address`: The address of the account that will send the transaction.
    - `receiver_address`: The address of the account that will be deleted.

    The function returns an AccountDelete object representing the created transaction.

    Note: Before executing this transaction, you must sign it with the appropriate private key and submit it to the XRP Ledger using a suitable library or API.
    """
    # Construct an AccountDelete operation
    return AccountDelete(
        account=sender_address,
        destination=receiver_address,
        last_ledger_sequence=int(last_ledger_sequence)  # Set the custom LastLedgerSequence
    )


def create_account_lines_response(paginated_transactions, paginator):
    return JsonResponse({
        "status": "success",
        "message": "Account Lines successfully retrieved.",
        "account_lines": list(paginated_transactions),
        "total_account_lines": paginator.count,
        "pages": paginator.num_pages,
        "current_page": paginated_transactions.number,
    })


def account_config_settings(response):
    return JsonResponse({
        "status": "success",
        "message": "Account configuration retrieved successfully.",
        "result": response,
    })


def prepare_account_tx_with_pagination(sender_address, marker):
    """
    Prepares an AccountTx transaction for the XRPL with pagination parameters.

    Args:
        sender_address (str): The address of the account to query transactions for.
        marker (any): A marker value used for pagination to retrieve the next set of transactions.

    Returns:
        xrpl.models.transactions.AccountTx: An AccountTx transaction object configured with the specified parameters.

    This function constructs an AccountTx transaction for the XRPL, which is used to retrieve transactions associated with a specific account.
    It takes two arguments: `sender_address`, which is the address of the account whose transactions are being queried, and `marker`,
    which is a marker value used for pagination. The function returns an `AccountTx` object configured with these parameters:
    - `ledger_index_min` and `ledger_index_max` set to `-1` indicate that all ledgers should be considered.
    - `limit` set to `100` specifies the maximum number of transactions to return in a single response.
    - `marker` is used for pagination, allowing retrieval of subsequent pages of transactions.
    """
    # Prepare and return an AccountTx transaction object with pagination parameters
    return AccountTx(
        account=sender_address,
        ledger_index_min=-1,
        ledger_index_max=-1,
        limit=100,
        marker=marker,
    )


def prepare_account_set_tx(sender_address, flags):
    return AccountSet(
        account=sender_address,
        flags=flags
    )



def prepare_account_lines(wallet_address, marker):
    return AccountLines(
        account=wallet_address,
        limit=100,
        marker=marker,
        ledger_index="validated",
    )


def prepare_account_lines_for_offer(wallet_address):
    return AccountLines(
        account=wallet_address,
        ledger_index="validated",
    )


def prepare_account_tx(sender_address):
    """
    Prepares an `AccountTx` request object to fetch transactions for a given sender address.

    This function creates and returns an `AccountTx` object configured to retrieve
    the transaction history for the specified sender address. The limit is set to 100
    to fetch more transactions in a single request, reducing the need for multiple
    API calls.

    Args:
        sender_address (str): The XRP Ledger address of the sender whose transactions
                              are to be fetched.

    Returns:
        AccountTx: A configured `AccountTx` object ready to be used in a request.
s
    Example:
        account_tx_request = prepare_account_tx("rExampleAddress123")
        response = xrpl_client.request(account_tx_request)
    """
    return AccountTx(
        account=sender_address,
        limit=100  # Increase limit to fetch more transactions at once, reducing the need for multiple requests
    )


def prepare_account_offers(wallet_address):
    return AccountOffers(
        account=wallet_address,
        ledger_index="validated",
    )
