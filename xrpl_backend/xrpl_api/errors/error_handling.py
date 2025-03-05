import logging

from django.http import JsonResponse

logger = logging.getLogger('xrpl_app')


def handle_error(error_message, status_code, function_name):
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
            engine_result = response.result.get("error_message")
            if engine_result is None:
                engine_result = 'unknown'

        engine_result_message = response.result.get("engine_result_message", "")
        if engine_result_message or engine_result_message == '':
            engine_result_message = engine_result
    else:
        engine_result = 'None'
        engine_result_message = ""

    handle_engine_result(engine_result, engine_result_message)


def process_unexpected_error(response):
    if response is not None:
        # Extract the error code from the exception message
        error_message = str(response.args[0]).split(":")[1].strip()  # Added strip() to remove extra whitespace
        handle_unexpected_error(error_message)
    else:
        raise Exception("Unknown error occurred during transaction processing.")


def handle_unexpected_error(error_message):
    action = error_messages.get(error_message, lambda: raise_exception(f"Unknown error: {error_message}"))
    action()


def handle_engine_result(engine_result, engine_result_message):
    logger.error(f"Engine result received: {engine_result}, Message: {engine_result_message}")

    # Check if "Invalid field" is in any part of engine_result
    if isinstance(engine_result, str) and "Invalid" in engine_result:
        raise_exception({"message": engine_result_message or {engine_result_message}})

    # engine_result_actions = {
    #     "tesSUCCESS": lambda: return_success("Transaction is successful."),
    #     "Transaction not found.": lambda: return_success("Transaction not found."),
    #     "unknown": lambda: raise_exception("Transaction response was unsuccessful."),
    #     "None": lambda: raise_exception("Transaction response was None and unsuccessful."),
    #     "tefBAD_AUTH": lambda: raise_exception("Transaction's public key is not authorized."),
    #     "terRETRY": lambda: raise_exception("The transaction should be retried at a later time."),
    #     "terQUEUED": lambda: raise_exception("The transaction has been queued for processing."),
    #     "tecCLAIM": lambda: raise_exception("The fee was claimed but the transaction did not succeed."),
    #     "tecDIR_FULL": lambda: raise_exception("The directory node is full."),
    #     "tecFAILED_PROCESSING": lambda: raise_exception("The transaction failed to process."),
    #     "tecINSUF_RESERVE_LINE": lambda: raise_exception("Insufficient reserve to add the trust line."),
    #     "tecINSUF_RESERVE_OFFER": lambda: raise_exception("Insufficient reserve to create the offer."),
    #     "tecNO_DST": lambda: raise_exception("Destination account does not exist."),
    #     "tecNO_DST_INSUF_XRP": lambda: raise_exception("Destination account does not exist. Too little XRP sent to create it."),
    #     "tecNO_LINE_INSUF_RESERVE": lambda: raise_exception("No such line. Too little reserve to create it."),
    #     "tecNO_LINE_REDUNDANT": lambda: raise_exception("Redundant trust line."),
    #     "tecPATH_DRY": lambda: raise_exception("Path could not send partial amount."),
    #     "tecPATH_PARTIAL": lambda: raise_exception("Path could not send full amount."),
    #     "tecUNFUNDED": lambda: raise_exception("One of the participants in the transaction does not have enough funds."),
    #     "tecUNFUNDED_ADD": lambda: raise_exception("Insufficient balance to add to escrow."),
    #     "tecUNFUNDED_OFFER": lambda: raise_exception("Offer is unfunded."),
    #     "tecOVERSIZE": lambda: raise_exception("Object too large."),
    #     "tecCRYPTOCONDITION_ERROR": lambda: raise_exception("The crypto-condition is incorrect."),
    #     "tecINTERNAL": lambda: raise_exception("Internal error."),
    #     "temBAD_AMOUNT": lambda: raise_exception("The amount is invalid."),
    #     "temBAD_AUTH_MASTER": lambda: raise_exception("Authorization is not from the master key."),
    #     "temBAD_CURRENCY": lambda: raise_exception("The currency is invalid."),
    #     "temBAD_EXPIRATION": lambda: raise_exception("The expiration is invalid."),
    #     "temBAD_FEE": lambda: raise_exception("The fee is invalid."),
    #     "temBAD_ISSUER": lambda: raise_exception("The issuer is invalid."),
    #     "temBAD_LIMIT": lambda: raise_exception("The limit is invalid."),
    #     "temBAD_OFFER": lambda: raise_exception("The offer is invalid."),
    #     "temBAD_PATH": lambda: raise_exception("The path is invalid."),
    #     "temBAD_PATH_LOOP": lambda: raise_exception("The path loop is invalid."),
    #     "temBAD_REGKEY": lambda: raise_exception("The regular key is invalid."),
    #     "temBAD_SEND_XRP_LIMIT": lambda: raise_exception("The send XRP limit is invalid."),
    #     "temBAD_SEND_XRP_MAX": lambda: raise_exception("The send XRP max is invalid."),
    #     "temBAD_SEND_XRP_NO_DIRECT": lambda: raise_exception("The send XRP direct is invalid."),
    #     "temBAD_SEND_XRP_PARTIAL": lambda: raise_exception("The send XRP partial is invalid."),
    #     "temBAD_SEND_XRP_PATHS": lambda: raise_exception("The send XRP paths are invalid."),
    #     "temBAD_TICK_SIZE": lambda: raise_exception("The tick size is invalid."),
    #     "temBAD_TRANSACTION": lambda: raise_exception("The transaction is invalid."),
    #     "temBAD_TRANSFER_RATE": lambda: raise_exception("The transfer rate is invalid."),
    #     "temBAD_WALLET": lambda: raise_exception("The wallet is invalid."),
    #     "temDISABLED": lambda: raise_exception("The feature is disabled."),
    #     "temDST_NEEDED": lambda: raise_exception("The destination is needed."),
    #     "temINVALID": lambda: raise_exception("The transaction is invalid."),
    #     "temMALFORMED": lambda: raise_exception("The transaction is malformed."),
    #     "temREDUNDANT": lambda: raise_exception("The transaction is redundant."),
    #     "temSEQ_AND_TICK": lambda: raise_exception("The sequence and tick are invalid."),
    #     "temSEQ_ARITH": lambda: raise_exception("The sequence arithmetic is invalid."),
    #     "temSEQ_DISCRETE": lambda: raise_exception("The sequence is discrete."),
    #     "temSEQ_INCR": lambda: raise_exception("The sequence is incremental."),
    #     "temSEQ_PREV": lambda: raise_exception("The sequence is previous."),
    #     "temSEQ_SUB": lambda: raise_exception("The sequence is sub."),
    #     "temSEQ_UNCHANGED": lambda: raise_exception("The sequence is unchanged."),
    #     "temSIGNER": lambda: raise_exception("The signer is invalid."),
    #     "temUNCERTAIN": lambda: raise_exception("The transaction is uncertain."),
    #     "temUNKNOWN": lambda: raise_exception("The transaction is unknown."),
    #     "temUNSUPPORTED": lambda: raise_exception("The transaction is unsupported."),
    #     "temWRONG": lambda: raise_exception("The transaction is wrong."),
    #     "temXRP": lambda: raise_exception("The XRP amount is invalid."),
    #     "temXRP_PATHS": lambda: raise_exception("The XRP paths are invalid."),
    #     "temXRP_TO_NON_XRP": lambda: raise_exception("The XRP to non-XRP is invalid."),
    #     "temXRP_TO_XRP": lambda: raise_exception("The XRP to XRP is invalid."),
    #     "temXRP_TO_XRP_LIMIT": lambda: raise_exception("The XRP to XRP limit is invalid."),
    #     "temXRP_TO_XRP_MAX": lambda: raise_exception("The XRP to XRP max is invalid."),
    #     "temXRP_TO_XRP_NO_DIRECT": lambda: raise_exception("The XRP to XRP direct is invalid."),
    #     "temXRP_TO_XRP_PARTIAL": lambda: raise_exception("The XRP to XRP partial is invalid."),
    #     "temXRP_TO_XRP_PATHS": lambda: raise_exception("The XRP to XRP paths are invalid."),
    #     "temXRP_TO_XRP_TICK_SIZE": lambda: raise_exception("The XRP to XRP tick size is invalid."),
    #     "temXRP_TO_XRP_TRANSFER_RATE": lambda: raise_exception("The XRP to XRP transfer rate is invalid."),
    #     "temXRP_TO_XRP_WALLET": lambda: raise_exception("The XRP to XRP wallet is invalid."),
    #     "temXRP_WALLET": lambda: raise_exception("The XRP wallet is invalid."),
    # }

    # action = engine_result_actions.get(engine_result, lambda: print(f"Error: {engine_result}, Message: {engine_result_message}"))
    action = error_messages.get(engine_result,lambda: print(f"Error: {engine_result}, Message: {engine_result_message}"))
    action()


def raise_exception(message):
    raise Exception(message)


def return_success(message):
    return message

error_messages = {
    # Success messages
    "tesSUCCESS": lambda: return_success("Transaction is successful."),
    "Transaction not found.": lambda: return_success("Transaction not found."),

    # Unknown or None error messages
    "unknown": lambda: raise_exception("Transaction response was unsuccessful."),
    "None": lambda: raise_exception("Transaction response was None and unsuccessful."),

    # Transaction Engine Codes (tec)
    "tecAMM_ACCOUNT": lambda: raise_exception("The AMM account is invalid or does not exist."),
    "tecAMM_UNFUNDED": lambda: raise_exception("The AMM account is not funded."),
    "tecAMM_BALANCE": lambda: raise_exception("The AMM balance is insufficient for the operation."),
    "tecAMM_EMPTY": lambda: raise_exception("The AMM pool is empty and cannot perform the operation."),
    "tecAMM_FAILED": lambda: raise_exception("The AMM operation failed due to an internal error."),
    "tecAMM_INVALID_TOKENS": lambda: raise_exception("The AMM tokens provided are invalid."),
    "tecAMM_NOT_EMPTY": lambda: raise_exception("The AMM pool is not empty and cannot be deleted."),
    "tecCANT_ACCEPT_OWN_NFTOKEN_OFFER": lambda: raise_exception("Cannot accept your own NFToken offer."),
    "tecCLAIM": lambda: raise_exception("The claim operation failed."),
    "tecCLAIM_DUPLICATE": lambda: raise_exception("The claim ID is a duplicate."),
    "tecCLAIM_EXPIRED": lambda: raise_exception("The claim has expired."),
    "tecCLAIM_INVALID": lambda: raise_exception("The claim is invalid."),
    "tecCLAIM_PAYMENT": lambda: raise_exception("The claim payment failed."),
    "tecCRYPTOCONDITION_ERROR": lambda: raise_exception("The cryptographic condition is invalid or cannot be fulfilled."),
    "tecDIR_FULL": lambda: raise_exception("The directory is full and cannot accept new entries."),
    "tecDIR_EMPTY": lambda: raise_exception("The directory is empty."),
    "tecDUPLICATE": lambda: raise_exception("The transaction is a duplicate and has already been processed."),
    "tecDUPLICATE_SIGNER": lambda: raise_exception("The signer list contains duplicate entries."),
    "tecDST_TAG_NEEDED": lambda: raise_exception("A destination tag is required for this transaction."),
    "tecEMPTY_DID": lambda: raise_exception("The DID document is empty or invalid."),
    "tecEXPIRED": lambda: raise_exception("The transaction has expired."),
    "tecFAILED_PROCESSING": lambda: raise_exception("The transaction failed during processing."),
    "tecFROZEN": lambda: raise_exception("The account or asset is frozen and cannot be used."),
    "tecHAS_OBLIGATIONS": lambda: raise_exception("The account has obligations and cannot be deleted."),
    "tecINSUF_RESERVE_LINE": lambda: raise_exception("Insufficient reserve for the trust line."),
    "tecINSUF_RESERVE_OFFER": lambda: raise_exception("Insufficient reserve for the offer."),
    "tecINSUFF_FEE": lambda: raise_exception("Insufficient fee for the transaction."),
    "tecINSUFFICIENT_FUNDS": lambda: raise_exception("Insufficient funds to complete the transaction."),
    "tecINSUFFICIENT_PAYMENT": lambda: raise_exception("Insufficient payment amount."),
    "tecINSUFFICIENT_RESERVE": lambda: raise_exception("Insufficient reserve to complete the transaction."),
    "tecINTERNAL": lambda: raise_exception("An internal error occurred during processing."),
    "tecINVARIANT_FAILED": lambda: raise_exception("An invariant check failed during processing."),
    "tecINVALID_ACCOUNT_ID": lambda: raise_exception("The account ID is invalid."),
    "tecINVALID_AMM_TOKENS": lambda: raise_exception("The AMM tokens are invalid."),
    "tecINVALID_FLAG": lambda: raise_exception("The transaction flag is invalid."),
    "tecINVALID_ISSUER": lambda: raise_exception("The issuer is invalid."),
    "tecINVALID_OFFER": lambda: raise_exception("The offer is invalid."),
    "tecINVALID_PAYMENT": lambda: raise_exception("The payment is invalid."),
    "tecINVALID_SIGNATURE": lambda: raise_exception("The signature is invalid."),
    "tecINVALID_TRANSFER_RATE": lambda: raise_exception("The transfer rate is invalid."),
    "tecKILLED": lambda: raise_exception("The transaction was killed due to a fatal error."),
    "tecMAX_SEQUENCE_REACHED": lambda: raise_exception("The maximum sequence number has been reached."),
    "tecNEED_MASTER_KEY": lambda: raise_exception("The master key is required for this operation."),
    "tecNFTOKEN_BUY_SELL_MISMATCH": lambda: raise_exception("The NFToken buy and sell offers do not match."),
    "tecNFTOKEN_OFFER_TYPE_MISMATCH": lambda: raise_exception("The NFToken offer type is invalid."),
    "tecNO_ALTERNATIVE_KEY": lambda: raise_exception("No alternative key is set for the account."),
    "tecNO_AUTH": lambda: raise_exception("You are not authorized to perform this operation."),
    "tecNO_DST": lambda: raise_exception("The destination account does not exist."),
    "tecNO_DST_INSUF_XRP": lambda: raise_exception("The destination account does not exist and insufficient XRP is sent to create it."),
    "tecNO_ENTRY": lambda: raise_exception("The requested entry does not exist."),
    "tecNO_ISSUER": lambda: raise_exception("The issuer account does not exist."),
    "tecNO_LINE": lambda: raise_exception("The trust line does not exist."),
    "tecNO_LINE_INSUF_RESERVE": lambda: raise_exception("The trust line does not exist and insufficient reserve is available to create it."),
    "tecNO_LINE_REDUNDANT": lambda: raise_exception("The trust line is redundant and cannot be created."),
    "tecNO_PERMISSION": lambda: raise_exception("You do not have permission to perform this operation."),
    "tecNO_REGULAR_KEY": lambda: raise_exception("No regular key is set for the account."),
    "tecNO_SUITABLE_NFTOKEN_PAGE": lambda: raise_exception("No suitable NFToken page is available."),
    "tecNO_TARGET": lambda: raise_exception("The target account does not exist."),
    "tecOBJECT_NOT_FOUND": lambda: raise_exception("The requested object was not found."),
    "tecOVERSIZE": lambda: raise_exception("The transaction exceeds the maximum size limit."),
    "tecOWNERS": lambda: raise_exception("The account has owners and cannot be deleted."),
    "tecPATH_DRY": lambda: raise_exception("The payment path is dry and cannot be used."),
    "tecPATH_PARTIAL": lambda: raise_exception("The payment path is partial and cannot be used."),
    "tecTOO_SOON": lambda: raise_exception("The transaction is being processed too soon."),
    "tecUNFUNDED": lambda: raise_exception("The account is unfunded and cannot perform the operation."),
    "tecUNFUNDED_ADD": lambda: raise_exception("The account is unfunded and cannot add a trust line."),
    "tecUNFUNDED_PAYMENT": lambda: raise_exception("The account is unfunded and cannot make the payment."),
    "tecUNFUNDED_OFFER": lambda: raise_exception("The account is unfunded and cannot create the offer."),

    # Transaction Engine Failure Codes (tef)
    "tefALREADY": lambda: raise_exception("The transaction has already been processed."),
    "tefBAD_AUTH": lambda: raise_exception("The transaction authorization is invalid."),
    "tefBAD_AUTH_MASTER": lambda: raise_exception("The master key authorization is invalid."),
    "tefBAD_LEDGER": lambda: raise_exception("The ledger is invalid or corrupted."),
    "tefBAD_QUORUM": lambda: raise_exception("The quorum for the transaction is invalid."),
    "tefBAD_SIGNATURE": lambda: raise_exception("The transaction signature is invalid."),
    "tefEXCEPTION": lambda: raise_exception("An exception occurred during processing."),
    "tefFAILURE": lambda: raise_exception("The transaction failed due to an unknown error."),
    "tefINTERNAL": lambda: raise_exception("An internal error occurred during processing."),
    "tefINVARIANT_FAILED": lambda: raise_exception("An invariant check failed during processing."),
    "tefMASTER_DISABLED": lambda: raise_exception("The master key is disabled."),
    "tefMAX_LEDGER": lambda: raise_exception("The maximum ledger sequence has been reached."),
    "tefNFTOKEN_IS_NOT_TRANSFERABLE": lambda: raise_exception("The NFToken is not transferable."),
    "tefNO_AUTH_REQUIRED": lambda: raise_exception("No authorization is required for this operation."),
    "tefNO_TICKET": lambda: raise_exception("No ticket is available for the transaction."),
    "tefNOT_MULTI_SIGNING": lambda: raise_exception("The transaction is not multi-signed."),
    "tefPAST_SEQ": lambda: raise_exception("The transaction sequence number is in the past."),
    "tefTOO_BIG": lambda: raise_exception("The transaction is too large to process."),
    "tefWRONG_PRIOR": lambda: raise_exception("The transaction has the wrong priority."),

    # Transaction Engine Local Codes (tel)
    "telBAD_DOMAIN": lambda: raise_exception("The domain is invalid."),
    "telBAD_PATH_COUNT": lambda: raise_exception("The path count is invalid."),
    "telBAD_PUBLIC_KEY": lambda: raise_exception("The public key is invalid."),
    "telCAN_NOT_QUEUE": lambda: raise_exception("The transaction cannot be queued."),
    "telCAN_NOT_QUEUE_BALANCE": lambda: raise_exception("The transaction cannot be queued due to insufficient balance."),
    "telCAN_NOT_QUEUE_BLOCKS": lambda: raise_exception("The transaction cannot be queued due to block limits."),
    "telCAN_NOT_QUEUE_BLOCKED": lambda: raise_exception("The transaction cannot be queued because the account is blocked."),
    "telCAN_NOT_QUEUE_FEE": lambda: raise_exception("The transaction cannot be queued due to insufficient fee."),
    "telCAN_NOT_QUEUE_FULL": lambda: raise_exception("The transaction queue is full."),
    "telFAILED_PROCESSING": lambda: raise_exception("The transaction failed during processing."),
    "telINSUF_FEE_P": lambda: raise_exception("The transaction fee is insufficient."),
    "telLOCAL_ERROR": lambda: raise_exception("A local error occurred during processing."),
    "telNETWORK_ID_MAKES_TX_NON_CANONICAL": lambda: raise_exception("The network ID makes the transaction non-canonical."),
    "telNO_DST_PARTIAL": lambda: raise_exception("The destination account does not exist, and partial payment is not allowed."),
    "telREQUIRES_NETWORK_ID": lambda: raise_exception("The transaction requires a network ID."),
    "telWRONG_NETWORK": lambda: raise_exception("The transaction is for the wrong network."),

    # Transaction Engine Malformed Codes (tem)
    "temBAD_AMM_TOKENS": lambda: raise_exception("The AMM tokens are invalid."),
    "temBAD_AMOUNT": lambda: raise_exception("The amount is invalid."),
    "temBAD_AUTH_MASTER": lambda: raise_exception("The master key authorization is invalid."),
    "temBAD_CURRENCY": lambda: raise_exception("The currency is invalid."),
    "temBAD_EXPIRATION": lambda: raise_exception("The expiration is invalid."),
    "temBAD_FEE": lambda: raise_exception("The fee is invalid."),
    "temBAD_ISSUER": lambda: raise_exception("The issuer is invalid."),
    "temBAD_LIMIT": lambda: raise_exception("The limit is invalid."),
    "temBAD_NFTOKEN_TRANSFER_FEE": lambda: raise_exception("The NFToken transfer fee is invalid."),
    "temBAD_OFFER": lambda: raise_exception("The offer is invalid."),
    "temBAD_PATH": lambda: raise_exception("The path is invalid."),
    "temBAD_PATH_LOOP": lambda: raise_exception("The path contains a loop."),
    "temBAD_SEND_XRP_LIMIT": lambda: raise_exception("The XRP send limit is invalid."),
    "temBAD_SEND_XRP_MAX": lambda: raise_exception("The XRP send maximum is invalid."),
    "temBAD_SEND_XRP_NO_DIRECT": lambda: raise_exception("Direct XRP sending is not allowed."),
    "temBAD_SEND_XRP_PARTIAL": lambda: raise_exception("Partial XRP sending is not allowed."),
    "temBAD_SEND_XRP_PATHS": lambda: raise_exception("The XRP send paths are invalid."),
    "temBAD_SEQUENCE": lambda: raise_exception("The sequence number is invalid."),
    "temBAD_SIGNATURE": lambda: raise_exception("The signature is invalid."),
    "temBAD_SRC_ACCOUNT": lambda: raise_exception("The source account is invalid."),
    "temBAD_TRANSFER_RATE": lambda: raise_exception("The transfer rate is invalid."),
    "temCANNOT_PREAUTH_SELF": lambda: raise_exception("Cannot preauthorize your own account."),
    "temDST_IS_SRC": lambda: raise_exception("The destination is the same as the source."),
    "temDST_NEEDED": lambda: raise_exception("A destination is required."),
    "temINVALID": lambda: raise_exception("The transaction is invalid."),
    "temINVALID_COUNT": lambda: raise_exception("The count is invalid."),
    "temINVALID_FLAG": lambda: raise_exception("The flag is invalid."),
    "temMALFORMED": lambda: raise_exception("The transaction is malformed."),
    "temREDUNDANT": lambda: raise_exception("The transaction is redundant."),
    "temREDUNDANT_SEND_MAX": lambda: raise_exception("The SendMax field is redundant."),
    "temRIPPLE_EMPTY": lambda: raise_exception("The Ripple transaction is empty."),
    "temBAD_WEIGHT": lambda: raise_exception("The weight is invalid."),
    "temBAD_SIGNER": lambda: raise_exception("The signer is invalid."),
    "temBAD_QUORUM": lambda: raise_exception("The quorum is invalid."),
    "temUNCERTAIN": lambda: raise_exception("The transaction result is uncertain."),
    "temUNKNOWN": lambda: raise_exception("An unknown error occurred."),
    "temDISABLED": lambda: raise_exception("The transaction is disabled."),
	"temBAD_REGKEY": lambda: raise_exception("The regular key is invalid."),
	"temBAD_TICK_SIZE": lambda: raise_exception("The tick size is invalid."),
	"temBAD_TRANSACTION": lambda: raise_exception("The transaction is invalid."),
	"temBAD_WALLET": lambda: raise_exception("The wallet is invalid."),
	"temSEQ_AND_TICK": lambda: raise_exception("The sequence and tick are invalid."),
	"temSEQ_ARITH": lambda: raise_exception("The sequence arithmetic is invalid."),
	"temSEQ_DISCRETE": lambda: raise_exception("The sequence is discrete."),
	"temSEQ_INCR": lambda: raise_exception("The sequence is incremental."),
	"temSEQ_PREV": lambda: raise_exception("The sequence is previous."),
	"temSEQ_SUB": lambda: raise_exception("The sequence is sub."),
	"temSEQ_UNCHANGED": lambda: raise_exception("The sequence is unchanged."),
	"temSIGNER": lambda: raise_exception("The signer is invalid."),
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

    # Transaction Engine Retry Codes (ter)
    "terINSUF_FEE_B": lambda: raise_exception("Insufficient fee for the transaction."),
    "terNO_ACCOUNT": lambda: raise_exception("The account does not exist."),
    "terNO_AMM": lambda: raise_exception("The AMM does not exist."),
    "terNO_AUTH": lambda: raise_exception("You are not authorized to perform this operation."),
    "terNO_RIPPLE": lambda: raise_exception("The Ripple feature is not enabled."),
    "terOWNERS": lambda: raise_exception("The account has owners and cannot be deleted."),
    "terPRE_SEQ": lambda: raise_exception("The transaction sequence number is in the past."),
    "terPRE_TICKET": lambda: raise_exception("The ticket is in the past."),
    "terQUEUED": lambda: raise_exception("The transaction is queued for processing."),
    "terRETRY": lambda: raise_exception("The transaction should be retried."),
    "terSUBMITTED": lambda: raise_exception("The transaction has been submitted."),
}