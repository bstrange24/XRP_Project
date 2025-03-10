import logging

from django.http import JsonResponse
from xrpl.models import CheckCreate, IssuedCurrencyAmount, CheckCash, CheckCancel
from xrpl.utils import xrp_to_drops, ripple_time_to_datetime

from ..accounts.account_utils import prepare_account_object

logger = logging.getLogger('xrpl_app')


def get_checks_for_account(client, account):
    checks_dict = {}
    sent_checks = []
    received_checks = []

    req = prepare_account_object(account, "validated", "check")
    response = client.request(req)

    # Parse result
    if "account_objects" in response.result:
        account_checks = response.result["account_objects"]
        for check in account_checks:
            if check["SendMax"]:
                check_data = {"sender": check["Account"], "receiver": check["Destination"]}
                if "Expiration" in check:
                    check_data["expiry_date"] = str(ripple_time_to_datetime(check["Expiration"]))
                # check_data["amount"] = str(drops_to_xrp(check["SendMax"]['value']))
                check_data["check_id"] = check["index"]
                if check_data["sender"] == account:
                    sent_checks.append(check_data)
                elif check_data["sender"] != account:
                    received_checks.append(check_data)

            # Sort checks
            checks_dict["sent"] = sent_checks
            checks_dict["receive"] = received_checks
            logger.info(f"checks_dict: {checks_dict}")

            return True, response.result
        else:
            return False, None


def prepare_cash_token_check(sender_wallet_address, check_id, issued_currency_amount):
    return CheckCash(
        account=sender_wallet_address,
        check_id=check_id,
        amount=issued_currency_amount
    )


def prepare_cash_check(sender_wallet_address, check_id, cash_amount):
    return CheckCash(
        account=sender_wallet_address,
        check_id=check_id,
        amount=xrp_to_drops(float(cash_amount))
    )


def prepare_cancel_check(sender_wallet_address, check_id):
    return CheckCancel(
        account=sender_wallet_address,
        check_id=check_id,
    )


def prepare_issued_currency(token_name, token_issuer, amount_to_deliver):
    return IssuedCurrencyAmount(
        currency=token_name,
        issuer=token_issuer,
        value=amount_to_deliver
    )


def prepare_check_create(sender_wallet_address, check_receiver_address, issued_currency_amount, expiry_date):
    return CheckCreate(
        account=sender_wallet_address,
        destination=check_receiver_address,
        send_max=issued_currency_amount,
        expiration=expiry_date
    )


def prepare_xrp_check_create(sender_wallet_address, check_receiver_address, amount_to_deliver, expiry_date):
    return CheckCreate(
        account=sender_wallet_address,
        destination=check_receiver_address,
        send_max=amount_to_deliver,
        expiration=expiry_date
    )


def get_checks_response(response, checks_created):
    if checks_created:
        return JsonResponse({
            "status": "success",
            "message": "Checks retrieved successfully.",
            "result": response
        })
    else:
        return JsonResponse({
            "status": "success",
            "message": "No checks found for this account.",
        })


def get_checks_pagination_response(paginated_transactions, paginator, checks_created):
    if checks_created:
        return JsonResponse({
            "status": "success",
            "message": "Checks retrieved for account.",
            "checks": list(paginated_transactions),
            "page": paginated_transactions.number,
            "total_pages": paginator.num_pages,
            "total_count": paginator.count
        })
    else:
        return JsonResponse({
            "status": "success",
            "message": "No checks found for this account.",
        })


def create_token_check_response(response):
    return JsonResponse({
        "status": "success",
        "message": "Token check created successfully.",
        "result": response
    })
