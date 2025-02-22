import logging

from django.http import JsonResponse
from xrpl.models import Tx

logger = logging.getLogger('xrpl_app')


def prepare_tx(tx_hash):
    return Tx(transaction=tx_hash)


def transaction_status_response(response):
    return JsonResponse({
        'status': 'success',
        'transactions': f"{response.result['tx_json']['TransactionType']}",
        'result': response.result,
    })


def transaction_history_response(response):
    return JsonResponse({
        'status': 'success',
        'transactions': f"{response['tx_json']['TransactionType']}",
        'result': response,
    })
