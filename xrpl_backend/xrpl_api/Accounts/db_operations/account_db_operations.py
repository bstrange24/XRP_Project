import json
import logging

import django
from django.db import IntegrityError

# from ..account_utils import get_account_set_flags_for_database_transaction
from ..models.account_models import XrplAccountData, AccountConfigurationTransaction, AffectedNode, \
    TxJson, AccountConfigurationTransactionMeta
from ...utilities.utilities import get_account_set_flags_for_database_transaction

# from ...utilities.utilities import get_account_set_flags_for_database_transaction

logger = logging.getLogger('xrpl_app')


def save_account_data(response, balance):
    try:
        logger.info("Saving account to db")

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

        with django.db.transaction.atomic():
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
    except django.db.IntegrityError as e:
        logger.error(f"IntegrityError caught saving transaction history data: {e}")
    except django.db.DataError as e:
        logger.error(f"DataError caught saving transaction history data: {e}")
    except Exception as e:
        logger.error(f"Unexpected exception caught saving transaction history data: {e}")

def save_account_configuration_transaction(response, flags_to_enable):
    try:
        # Parse JSON
        result = json.loads(response) if isinstance(response, str) else response

        flag_mapping = get_account_set_flags_for_database_transaction(flags_to_enable)

        with django.db.transaction.atomic():
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
                    "set_flag": result["tx_json"].get("SetFlag") or result["tx_json"].get("Flag"),
                    "signing_pub_key": result["tx_json"]["SigningPubKey"],
                    "transaction_type": result["tx_json"]["TransactionType"],
                    "txn_signature": result["tx_json"]["TxnSignature"],
                    "date": result["tx_json"]["date"],
                    "ledger_index": result["tx_json"]["ledger_index"]
                }
            )

        return transaction
    except django.db.IntegrityError as e:
        logger.error(f"IntegrityError caught saving transaction history data: {e}")
    except django.db.DataError as e:
        logger.error(f"DataError caught saving transaction history data: {e}")
    except Exception as e:
        logger.error(f"Unexpected exception caught saving transaction history data: {e}")
