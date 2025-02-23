from django.http import JsonResponse
from xrpl.models import TrustSet, IssuedCurrencyAmount


def create_trust_set_transaction(currency_code, limit_drops, issuer_address, sender_wallet, sequence_number, fee, current_ledger):
    return TrustSet(
        account=sender_wallet,  # Set the sender wallet as the account for the transaction
        limit_amount=IssuedCurrencyAmount(
            currency=currency_code,  # The currency code for the trust line
            issuer=issuer_address,  # The issuer of the trust line
            value=str(limit_drops),
        ),
        sequence=sequence_number,
        fee=fee,
        last_ledger_sequence=current_ledger + 300  # Valid for ~60-100 seconds
    )


def create_trust_set_response(response, issuer, currency, limit):
    if limit == 'EMPTY_LIMIT':
        message = 'Trust line successfully removed'
        limit = ''
    else:
        message = 'Trust line set successfully.'
    return JsonResponse({
        'status': 'success',  # Indicate that the operation was successful
        'message': message,  # Provide a success message
        'result': response.result,  # Include the result from the XRPL transaction
        'issuer': issuer,  # Include the issuer address that had the trust line set
        'currency': currency,  # Include the currency code for the trust line
        'limit': limit,  # Include the limit for the trust line in drops
    })


def trust_line_response(response):
    return JsonResponse({
        'status': 'success',  # Indicate that the operation was successful
        'message': 'Trust lines fetched successfully.',  # Provide a success message
        'results': response.result  # Include the results from the XRPL transaction
    })
