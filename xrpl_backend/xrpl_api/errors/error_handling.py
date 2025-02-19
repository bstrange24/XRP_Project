import logging

from django.http import JsonResponse

logger = logging.getLogger('xrpl_app')


def handle_error(error_message, status_code, function_name):
    """
    This function handles error responses by logging the error, creating a JSON response, and returning it with an appropriate status code.
    - Logs the error message and function exit.
    - Constructs a JSON response with the error message.
    - Sets the HTTP status code based on the error context.
    Parameters:
    - error_message: The details of the error to be logged and returned.
    - status_code: HTTP status code to set for the response.
    - function_name: Name of the function where the error occurred for logging.
    """

    logger.error(error_message)
    logger.error(f"Leaving: {function_name}")
    return JsonResponse(error_message, status=status_code)


def error_response(message):
    return {"status": "failure", "message": message}


def handle_error_new(exception, status_code, function_name):
    exception_name = type(exception).__name__
    logger.error(f"Exception caught: {exception_name} - {exception}")

    error_data = exception.args[0] if exception.args and isinstance(exception.args[0], dict) else {"status": "failure", "message": str(exception)}

    logger.error(f"Leaving: {function_name}")
    return JsonResponse(error_data, status=status_code)


def process_transaction_error(response):
    if response is not None:
        engine_result = response.result.get("engine_result")
        if engine_result is None:
            engine_result = 'unknown'

        engine_result_message = response.result.get("engine_result_message", "")
    else:
        engine_result = 'None'
        engine_result_message = ""

    handle_engine_result(engine_result, engine_result_message)


def handle_engine_result(engine_result, engine_result_message):
    """
    Handle the engine result by performing the appropriate action based on the result code.
    """
    engine_result_actions = {
        "tesSUCCESS": lambda: return_success("Transaction is successful."),
        "unknown": lambda: raise_exception("Transaction response was unsuccessful."),
        "None": lambda: raise_exception("Transaction response was None and unsuccessful."),
        "tefBAD_AUTH": lambda: raise_exception("Transaction's public key is not authorized."),
        "tecNO_LINE_INSUF_RESERVE": lambda: raise_exception("No such line. Too little reserve to create it."),
        "terRETRY": lambda: raise_exception("The transaction should be retried at a later time."),
        "terQUEUED": lambda: raise_exception("The transaction has been queued for processing."),
        "tecCLAIM": lambda: raise_exception("The fee was claimed but the transaction did not succeed."),
        "tecDIR_FULL": lambda: raise_exception("The directory node is full."),
        "tecFAILED_PROCESSING": lambda: raise_exception("The transaction failed to process."),
        "tecINSUF_RESERVE_LINE": lambda: raise_exception("Insufficient reserve to add the trust line."),
        "tecINSUF_RESERVE_OFFER": lambda: raise_exception("Insufficient reserve to create the offer."),
        "tecNO_DST": lambda: raise_exception("Destination account does not exist."),
        "tecNO_DST_INSUF_XRP": lambda: raise_exception("Destination account does not exist. Too little XRP sent to create it."),
        "tecNO_LINE_INSUF_RESERVE": lambda: raise_exception("No such line. Too little reserve to create it."),
        "tecNO_LINE_REDUNDANT": lambda: raise_exception("Redundant trust line."),
        "tecPATH_DRY": lambda: raise_exception("Path could not send partial amount."),
        "tecPATH_PARTIAL": lambda: raise_exception("Path could not send full amount."),
        "tecUNFUNDED": lambda: raise_exception("One of the participants in the transaction does not have enough funds."),
        "tecUNFUNDED_ADD": lambda: raise_exception("Insufficient balance to add to escrow."),
        "tecUNFUNDED_OFFER": lambda: raise_exception("Offer is unfunded."),
        "tecOVERSIZE": lambda: raise_exception("Object too large."),
        "tecCRYPTOCONDITION_ERROR": lambda: raise_exception("The crypto-condition is incorrect."),
        "tecINTERNAL": lambda: raise_exception("Internal error."),
        "temBAD_AMOUNT": lambda: raise_exception("The amount is invalid."),
        "temBAD_AUTH_MASTER": lambda: raise_exception("Authorization is not from the master key."),
        "temBAD_CURRENCY": lambda: raise_exception("The currency is invalid."),
        "temBAD_EXPIRATION": lambda: raise_exception("The expiration is invalid."),
        "temBAD_FEE": lambda: raise_exception("The fee is invalid."),
        "temBAD_ISSUER": lambda: raise_exception("The issuer is invalid."),
        "temBAD_LIMIT": lambda: raise_exception("The limit is invalid."),
        "temBAD_OFFER": lambda: raise_exception("The offer is invalid."),
        "temBAD_PATH": lambda: raise_exception("The path is invalid."),
        "temBAD_PATH_LOOP": lambda: raise_exception("The path loop is invalid."),
        "temBAD_REGKEY": lambda: raise_exception("The regular key is invalid."),
        "temBAD_SEND_XRP_LIMIT": lambda: raise_exception("The send XRP limit is invalid."),
        "temBAD_SEND_XRP_MAX": lambda: raise_exception("The send XRP max is invalid."),
        "temBAD_SEND_XRP_NO_DIRECT": lambda: raise_exception("The send XRP direct is invalid."),
        "temBAD_SEND_XRP_PARTIAL": lambda: raise_exception("The send XRP partial is invalid."),
        "temBAD_SEND_XRP_PATHS": lambda: raise_exception("The send XRP paths are invalid."),
        "temBAD_TICK_SIZE": lambda: raise_exception("The tick size is invalid."),
        "temBAD_TRANSACTION": lambda: raise_exception("The transaction is invalid."),
        "temBAD_TRANSFER_RATE": lambda: raise_exception("The transfer rate is invalid."),
        "temBAD_WALLET": lambda: raise_exception("The wallet is invalid."),
        "temDISABLED": lambda: raise_exception("The feature is disabled."),
        "temDST_NEEDED": lambda: raise_exception("The destination is needed."),
        "temINVALID": lambda: raise_exception("The transaction is invalid."),
        "temMALFORMED": lambda: raise_exception("The transaction is malformed."),
        "temREDUNDANT": lambda: raise_exception("The transaction is redundant."),
        "temSEQ_AND_TICK": lambda: raise_exception("The sequence and tick are invalid."),
        "temSEQ_ARITH": lambda: raise_exception("The sequence arithmetic is invalid."),
        "temSEQ_DISCRETE": lambda: raise_exception("The sequence is discrete."),
        "temSEQ_INCR": lambda: raise_exception("The sequence is incremental."),
        "temSEQ_PREV": lambda: raise_exception("The sequence is previous."),
        "temSEQ_SUB": lambda: raise_exception("The sequence is sub."),
        "temSEQ_UNCHANGED": lambda: raise_exception("The sequence is unchanged."),
        "temSIGNER": lambda: raise_exception("The signer is invalid."),
        "temUNCERTAIN": lambda: raise_exception("The transaction is uncertain."),
        "temUNKNOWN": lambda: raise_exception("The transaction is unknown."),
        "temUNSUPPORTED": lambda: raise_exception("The transaction is unsupported."),
        "temWRONG": lambda: raise_exception("The transaction is wrong."),
        "temXRP": lambda: raise_exception("The XRP amount is invalid."),
        "temXRP_PATHS": lambda: raise_exception("The XRP paths are invalid."),
        "temXRP_TO_NON_XRP": lambda: raise_exception("The XRP to non-XRP is invalid."),
        "temXRP_TO_XRP": lambda: raise_exception("The XRP to XRP is invalid."),
        "temXRP_TO_XRP_LIMIT": lambda: raise_exception("The XRP to XRP limit is invalid."),
        "temXRP_TO_XRP_MAX": lambda: raise_exception("The XRP to XRP max is invalid."),
        "temXRP_TO_XRP_NO_DIRECT": lambda: raise_exception("The XRP to XRP direct is invalid."),
        "temXRP_TO_XRP_PARTIAL": lambda: raise_exception("The XRP to XRP partial is invalid."),
        "temXRP_TO_XRP_PATHS": lambda: raise_exception("The XRP to XRP paths are invalid."),
        "temXRP_TO_XRP_TICK_SIZE": lambda: raise_exception("The XRP to XRP tick size is invalid."),
        "temXRP_TO_XRP_TRANSFER_RATE": lambda: raise_exception("The XRP to XRP transfer rate is invalid."),
        "temXRP_TO_XRP_WALLET": lambda: raise_exception("The XRP to XRP wallet is invalid."),
        "temXRP_WALLET": lambda: raise_exception("The XRP wallet is invalid."),
    }

    action = engine_result_actions.get(engine_result, lambda: print(f"Error: {engine_result}, Message: {engine_result_message}"))
    action()


def raise_exception(message):
    """
    Raise an exception with the given message.
    """
    raise Exception(message)


def return_success(message):
    """
    Return success message.
    """
    return message