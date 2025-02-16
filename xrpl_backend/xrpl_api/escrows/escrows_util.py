# Function to check for Escrow entries
import json
import logging

logger = logging.getLogger('xrpl_app')


def check_escrow_entries(account_objects):
    # Filter escrow entries
    escrow_entries = [entry for entry in account_objects if entry.get('LedgerEntryType') == 'Escrow']

    if escrow_entries:
        logger.error(f"Escrow entries found: {json.dumps(escrow_entries, indent=2)}")
        return False

    logger.info("No Escrow entries found.")
    return True
