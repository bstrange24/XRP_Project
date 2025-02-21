import json
import logging

# from ..models import XrplAccountData
from django.db import IntegrityError

from ..models.account_models import XrplAccountData, AccountConfigurationTransaction, AffectedNode, \
    TxJson, AccountConfigurationTransactionMeta

logger = logging.getLogger('xrpl_app')


def save_account_data_to_databases(response, balance):
    """
    Save account data retrieved from XRPL to the database.

    This function processes the response data from XRPL, validates the required fields,
    and saves the account information along with its flags into the database.

    Args:
        response (dict): The XRPL response containing account information.
        balance (str): The balance of the account.

    Raises:
        ValueError: If the response is missing required data or if there is a database integrity error.

    Workflow:
    1. Parse the response JSON into a Python dictionary.
    2. Validate the presence of the required keys in the `account_data` and `account_flags`.
    3. Create an instance of the `XrplAccountData` model and save it to the database.
    4. Handle and log errors such as missing keys, database constraints, or unexpected exceptions.
    """

    try:
        logger.info("Saving account to db")

        # Parse the JSON string into Python dictionary
        # json_string = json.dumps(response, indent=4)
        # data = json.loads(json_string)
        data = response
        # Ensure required keys exist in the response data
        if 'account_data' not in data or 'account_flags' not in data:
            raise KeyError("Missing expected 'account_data' or 'account_flags' in the response.")

        account_data = data['account_data']
        account_flags = data['account_flags']

        # Ensure required fields are in the account_data and account_flags
        required_account_data_keys = [
            'Account', 'Flags', 'LedgerEntryType', 'OwnerCount', 'PreviousTxnID',
            'PreviousTxnLgrSeq', 'Sequence', 'index'
        ]
        required_account_flags_keys = [
            'allowTrustLineClawback', 'defaultRipple', 'depositAuth', 'disableMasterKey',
            'disallowIncomingCheck', 'globalFreeze', 'noFreeze', 'passwordSpent',
            'requireAuthorization', 'requireDestinationTag'
        ]

        # Check if all required keys are present
        for key in required_account_data_keys:
            if key not in account_data:
                raise KeyError(f"Missing '{key}' in account_data.")

        for key in required_account_flags_keys:
            if key not in account_flags:
                raise KeyError(f"Missing '{key}' in account_flags.")

        # Create and save the account instance
        account = XrplAccountData.objects.create(
            account=account_data['Account'],
            balance=balance,
            flags=account_data['Flags'],
            ledger_entry_type=account_data['LedgerEntryType'],
            owner_count=account_data['OwnerCount'],
            previous_txn_id=account_data['PreviousTxnID'],
            previous_txn_lgr_seq=account_data['PreviousTxnLgrSeq'],
            sequence=account_data['Sequence'],
            index=account_data['index'],

            # Account flags
            allow_trustline_clawback=account_flags['allowTrustLineClawback'],
            default_ripple=account_flags['defaultRipple'],
            deposit_auth=account_flags['depositAuth'],
            disable_master_key=account_flags['disableMasterKey'],
            disallow_incoming_check=account_flags['disallowIncomingCheck'],
            global_freeze=account_flags['globalFreeze'],
            no_freeze=account_flags['noFreeze'],
            password_spent=account_flags['passwordSpent'],
            require_authorization=account_flags['requireAuthorization'],
            require_destination_tag=account_flags['requireDestinationTag'],

            # Ledger-related
            ledger_hash=data.get('ledger_hash', ''),
            ledger_index=data.get('ledger_index', ''),
            validated=data.get('validated', False)
        )

        logger.info(f"Account {account.account} created and saved.")
    except IntegrityError as e:
        # Handle database constraint violations
        logger.error(f"Database error saving account to DB: {str(e)}")
        raise ValueError(f"Database integrity error: {str(e)}")
    except KeyError as e:
        # Handle missing keys in the response
        logger.error(f"Error saving account to DB: Missing expected key: {str(e)}")
        raise ValueError(f"Missing expected data: {str(e)}")
    except Exception as e:
        # Catch any other errors (e.g., database errors)
        logger.error(f"Error saving account to DB: {str(e)}")
        raise ValueError(f"Error saving account to database: {str(e)}")


def save_account_configuration_transaction(response, all_flags):
    # Parse JSON
    data = json.loads(response) if isinstance(response, str) else response
    result = data

    # Create a set of enabled flag names for faster lookup
    enabled_flags = {flag.name for flag in all_flags}  # all_flags is actually flags_to_enable + flags_to_disable

    # Here, decide on your universe of flags. For instance:
    all_possible_flags = {
        "ASF_ACCOUNT_TXN_ID": "asf_account_txn_id",
        "ASF_ALLOW_TRUSTLINE_CLAWBACK": "asf_allow_trustline_clawback",
        "ASF_AUTHORIZED_NFTOKEN_MINTER": "asf_authorized_nftoken_minter",
        "ASF_DEFAULT_RIPPLE": "asf_default_ripple",
        "ASF_DEPOSIT_AUTH": "asf_deposit_auth",
        "ASF_DISABLE_MASTER": "asf_disable_master",
        "ASF_DISABLE_INCOMING_CHECK": "asf_disable_incoming_check",
        "ASF_DISABLE_INCOMING_NFTOKEN_OFFER": "asf_disable_incoming_nftoken_offer",
        "ASF_DISABLE_INCOMING_PAYCHAN": "asf_disable_incoming_paychan",
        "ASF_DISABLE_INCOMING_TRUSTLINE": "asf_disable_incoming_trustline",
        "ASF_DISALLOW_XRP": "asf_disallow_XRP",
        "ASF_GLOBAL_FREEZE": "asf_global_freeze",
        "ASF_NO_FREEZE": "asf_no_freeze",
        "ASF_REQUIRE_AUTH": "asf_require_auth",
        "ASF_REQUIRE_DEST": "asf_require_dest",
    }

    # Build a dictionary mapping model field names to booleans
    # For simplicity, assume that if a flag is in enabled_flags, then it's True; otherwise, it's False.
    flag_mapping = {}
    for enum_name, model_field in all_possible_flags.items():
        flag_mapping[model_field] = enum_name in enabled_flags

    # Upsert AccountTransaction
    transaction, created = AccountConfigurationTransaction.objects.update_or_create(
        asf_account_txn_id = flag_mapping.get('asf_account_txn_id'),
        asf_allow_trustline_clawback = flag_mapping.get('asf_allow_trustline_clawback'),
        asf_authorized_nftoken_minter = flag_mapping.get('asf_authorized_nftoken_minter'),
        asf_default_ripple = flag_mapping.get('asf_default_ripple'),
        asf_deposit_auth = flag_mapping.get('asf_deposit_auth'),
        asf_disable_master = flag_mapping.get('asf_disable_master'),
        asf_disable_incoming_check = flag_mapping.get('asf_disable_incoming_check'),
        asf_disable_incoming_nftoken_offer = flag_mapping.get('asf_disable_incoming_nftoken_offer'),
        asf_disable_incoming_paychan = flag_mapping.get('asf_disable_incoming_paychan'),
        asf_disable_incoming_trustline = flag_mapping.get('asf_disable_incoming_trustline'),
        asf_disallow_xrp = flag_mapping.get('asf_disallow_XRP'),
        asf_global_freeze = flag_mapping.get('asf_global_freeze'),
        asf_no_freeze = flag_mapping.get('asf_no_freeze'),
        asf_require_auth = flag_mapping.get('asf_require_auth'),
        asf_require_dest = flag_mapping.get('asf_require_dest'),
        hash=result["hash"],
        defaults={
            "close_time_iso": result["close_time_iso"],
            "ctid": result["ctid"],
            "ledger_hash": result["ledger_hash"],
            "ledger_index": result["ledger_index"],
            "validated": result["validated"]
        }
    )

    # Upsert AccountConfigurationTransactionMeta
    AccountConfigurationTransactionMeta.objects.update_or_create(
        transaction=transaction,
        defaults={
            "transaction_index": result["meta"]["TransactionIndex"],
            "transaction_result": result["meta"]["TransactionResult"]
        }
    )

    # Upsert AffectedNodes (delete existing and recreate to ensure accuracy)
    AffectedNode.objects.filter(meta=transaction.meta).delete()
    for node in result["meta"]["AffectedNodes"]:
        modified_node = node["ModifiedNode"]
        AffectedNode.objects.create(
            meta=transaction.meta,
            ledger_entry_type=modified_node["LedgerEntryType"],
            ledger_index=modified_node["LedgerIndex"],
            final_fields=modified_node["FinalFields"],
            previous_fields=modified_node.get("PreviousFields"),
            previous_txn_id=modified_node.get("PreviousTxnID"),
            previous_txn_lgr_seq=modified_node.get("PreviousTxnLgrSeq")
        )

    # Upsert TxJson
    TxJson.objects.update_or_create(
        transaction=transaction,
        defaults={
            "account": result["tx_json"]["Account"],
            "fee": result["tx_json"]["Fee"],
            "flags": result["tx_json"]["Flags"],
            "last_ledger_sequence": result["tx_json"]["LastLedgerSequence"],
            "sequence": result["tx_json"]["Sequence"],
            "set_flag": result["tx_json"].get("SetFlag"),
            "signing_pub_key": result["tx_json"]["SigningPubKey"],
            "transaction_type": result["tx_json"]["TransactionType"],
            "txn_signature": result["tx_json"]["TxnSignature"],
            "date": result["tx_json"]["date"],
            "ledger_index": result["tx_json"]["ledger_index"]
        }
    )

    return transaction