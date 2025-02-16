from django.http import JsonResponse
from xrpl.models import TrustSet, IssuedCurrencyAmount

def create_trust_set_transaction(currency, limit_drops, wallet_address, sender_wallet, sequence_number, fee):
    """
    Creates a TrustSet transaction for setting a trust line on the XRPL.

    Args:
        currency (str): The currency code for the trust line (e.g., 'USD').
        limit_drops (str): The limit for the trust line in drops (1 drop = 0.000001 XRP).
        wallet_address (str): The address of the wallet that is setting the trust line.
        sender_wallet (Wallet): The wallet object representing the sender.
        sequence_number (int): The current sequence number of the sender's account.
        fee (str): The transaction fee in drops.

    Returns:
        TrustSet: A TrustSet transaction object ready to be submitted to the XRPL.
    """
    return TrustSet(
        account=sender_wallet,  # Set the sender wallet as the account for the transaction
        limit_amount=IssuedCurrencyAmount(  # Properly instantiate IssuedCurrencyAmount
            currency=currency,  # The currency code for the trust line
            value=str(limit_drops),  # Ensure the value is a string
            issuer=wallet_address,  # The issuer of the trust line
        ),
        sequence=sequence_number,  # Add the sequence number here
        fee=fee,  # Add the fee here
    )


def create_trust_set_response(response, account, currency, limit):
    """
    Creates a JSON response for successful trust line set operations.

    Args:
        response (xrpl.models.response.Response): The response object from the XRPL transaction.
        account (str): The address of the account that had the trust line set.
        currency (str): The currency code for the trust line.
        limit (str): The limit for the trust line in drops.

    Returns:
        JsonResponse: A Django JsonResponse containing the success message and transaction details.
    """
    # Create a JSON response with success status, message, and transaction details
    return JsonResponse({
        'status': 'success',  # Indicate that the operation was successful
        'message': 'Trust line set successfully.',  # Provide a success message
        'result': response.result,  # Include the result from the XRPL transaction
        'account': account,  # Include the account address that had the trust line set
        'currency': currency,  # Include the currency code for the trust line
        'limit': limit,  # Include the limit for the trust line in drops
    })


def trust_line_response(response):
    """
    Creates a JSON response for successfully fetching trust lines.

    Args:
        response (xrpl.models.response.Response): The response object from the XRPL transaction to fetch trust lines.

    Returns:
        JsonResponse: A Django JsonResponse containing the success message and fetched trust line details.
    """
    # Create a JSON response with success status, message, and fetched trust line details
    return JsonResponse({
        'status': 'success',  # Indicate that the operation was successful
        'message': 'Trust lines fetched successfully.',  # Provide a success message
        'results': response.result  # Include the results from the XRPL transaction
    })
