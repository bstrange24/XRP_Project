import json

from django.http import JsonResponse
from xrpl.models import LedgerEntry, DIDSet, DIDDelete
from xrpl.utils import str_to_hex
from typing import Dict, Optional, Tuple
from jsonschema import validate, ValidationError
from ..constants.constants import MAX_DID_DOCUMENT_SIZE, MAX_URI_SIZE, DID_SCHEMA


def validate_did_set_data(did_document: Optional[Dict] = None, uri: Optional[str] = None) -> Tuple[bool, str]:
    """
    Validate data for a DIDSet transaction on the XRPL.

    Args:
        did_document (Optional[Dict]): DID document to embed in the transaction.
        uri (Optional[str]): URI pointing to an external DID document.

    Returns:
        Tuple[bool, str]: (is_valid, message) indicating if the data is valid and any error message.
    """
    # Check that at least one of DIDDocument or URI is provided
    if did_document is None and uri is None:
        return False, "Either DIDDocument or URI must be provided."

    # Validate DIDDocument if provided
    if did_document is not None:
        try:
            # Convert to JSON string to check size
            did_doc_str = json.dumps(did_document)
            if len(did_doc_str.encode("utf-8")) > MAX_DID_DOCUMENT_SIZE:
                return False, f"DIDDocument exceeds size limit of {MAX_DID_DOCUMENT_SIZE} bytes."

            # Validate against W3C DID schema
            validate(instance=did_document, schema=DID_SCHEMA)

            # Additional XRPL-specific checks
            did_id = did_document.get("id")
            if not did_id:
                return False, "DID document must have an 'id' field."
            if not did_id.startswith("did:xrpl:1:"):
                return False, "DID 'id' must use 'did:xrpl:1:' method."

            # Check public key length (66 hex chars for 33-byte Ed25519 pubkey)
            pubkey = did_id[len("did:xrpl:1:"):]
            if len(pubkey) != 66 or not all(c in "0123456789abcdefABCDEF" for c in pubkey):
                return False, "DID 'id' public key must be 66 hex characters."

        except json.JSONDecodeError:
            return False, "DIDDocument must be valid JSON."
        except ValidationError as e:
            return False, f"DIDDocument validation failed: {str(e)}"

    # Validate URI if provided
    if uri is not None:
        if not isinstance(uri, str):
            return False, "URI must be a string."
        if len(uri.encode("utf-8")) > MAX_URI_SIZE:
            return False, f"URI exceeds size limit of {MAX_URI_SIZE} bytes."
        # Optional: Add regex or custom logic to validate URI format (e.g., IPFS CID)
        if not uri.startswith(("http://", "https://", "ipfs://")):
            return False, "URI must start with a valid scheme (http://, https://, ipfs://)."

    # Ensure DIDDocument and URI aren't both oversized or conflicting
    if did_document and uri:
        return False, "Only one of DIDDocument or URI should be provided, not both."

    return True, "DIDSet data is valid."

def prepare_ledger_entry(creator_account, ledger_index_status ):
    return LedgerEntry(
        ledger_index=ledger_index_status,
        did=creator_account
    )

def prepare_did_set(creator_address, document, data, uri):
    # str_to_hex() converts the inputted string to blockchain understandable hexadecimal
    return DIDSet(
        account=creator_address,
        did_document=str_to_hex(document),
        data=str_to_hex(data),
        uri=str_to_hex(uri),
    )

def prepare_did_delete(creator_address):
    return DIDDelete(
        account=creator_address,
    )

def set_did_response(response):
    return JsonResponse({
        "status": "success",
        "message": "DID successfully created.",
        "result": response
    })

def delete_did_response(response):
    return JsonResponse({
        "status": "success",
        "message": "DID successfully deleted.",
        "result": response
    })

def did_response(response, account_created):
    if account_created:
        return JsonResponse({
            "status": "success",
            "message": "DID retrieved successfully.",
            "result": response,
        })
    else:
        return JsonResponse({
            "status": "success",
            "message": "No DID found for this account.",
        })


