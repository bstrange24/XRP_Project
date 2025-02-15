import json
import logging

from .models import XrplAccountData
from django.db import IntegrityError

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
        json_string = json.dumps(response, indent=4)
        data = json.loads(json_string)
        data= data['result']
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
