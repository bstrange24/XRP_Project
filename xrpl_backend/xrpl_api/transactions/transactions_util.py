import logging

from django.http import JsonResponse
from xrpl.models import Tx

logger = logging.getLogger('xrpl_app')


def prepare_tx(tx_hash):
    return Tx(transaction=tx_hash)


def transaction_status_response(response, tx_hash):
    return JsonResponse({
        'status': 'success',
        'message': f"{response.result['tx_json']['TransactionType']}",
        'result': response.result,
    })


def transaction_history_response(transaction_tx):
    return JsonResponse({
        'status': 'success',
        'message': 'Transaction history successfully retrieved.',
        'response': transaction_tx,
    })
