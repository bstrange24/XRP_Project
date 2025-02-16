import logging

from django.http import JsonResponse
from xrpl.models import Tx

logger = logging.getLogger('xrpl_app')

def prepare_tx(tx_hash):
    """
    Prepares a `Tx` request object to fetch details of a specific transaction.

    This function creates and returns a `Tx` object configured to retrieve
    the details of a transaction identified by its transaction hash. The
    transaction hash is used to query the XRP Ledger for the corresponding
    transaction data.

    Args:
        tx_hash (str): The transaction hash (ID) of the transaction to fetch.

    Returns:
        Tx: A configured `Tx` object ready to be used in a request.

    Example:
        tx_request = prepare_tx("ABC123TransactionHashXYZ")
        response = xrpl_client.request(tx_request)
    """
    return Tx(transaction=tx_hash)


def transaction_status_response(response, tx_hash):
    """
    Constructs a JSON response for the status of a transaction.

    Args:
        response (xrpl.models.response.Response): The response from the XRPL client containing transaction details.
        tx_hash (str): The hash of the transaction whose status is being retrieved.

    Returns:
        JsonResponse: A Django JsonResponse object containing the result of the transaction status retrieval.

    This function prepares a JSON response for retrieving the status of a specific transaction, including the status and message of the operation.
    It takes two arguments:
    - `response`: The response from the XRPL client, which contains details about the transaction.
    - `tx_hash`: The hash of the transaction whose status is being retrieved.

    The function returns a Django JsonResponse object with keys for 'status', 'message', and 'result'.
    - 'status' indicates the outcome of the operation ('success' or an error message).
    - 'message' provides a brief description of the operation result.
    - 'result' contains the actual response from the XRPL client regarding the transaction status.

    This allows for a consistent format to inform clients about whether the transaction status was successfully retrieved and provide additional details if needed.
    """
    # Log successful retrieval of transaction status
    logger.info(f"Transaction status retrieved successfully for hash: {tx_hash}")

    # Prepare and return a JSON response for the transaction status
    return JsonResponse({
        'status': 'success',
        'message': 'Payment successfully sent.',
        'result': response.result,  # Corrected from 'response.result' to 'result'
    })


def transaction_history_response(transaction_tx):
    # Prepare and return a JSON response for the transaction history
    return JsonResponse({
        'status': 'success',
        'message': 'Transaction history successfully retrieved.',
        'response': transaction_tx,
    })