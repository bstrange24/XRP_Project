import logging

from xrpl.models.transactions import AccountSet

logger = logging.getLogger('xrpl_app')

MAX_RETRIES = 3  # Maximum retry attempts
RETRY_BACKOFF = 2  # Exponential backoff base in seconds

PAGINATION_PAGE_SIZE = 10

CACHE_TIMEOUT = 60  # 1 minute cache timeout
CACHE_TIMEOUT_FOR_TRUST_LINES = 300
CACHE_TIMEOUT_FOR_GET_OFFERS = 10  # 10 seconds
CACHE_TIMEOUT_FOR_SERVER_INFO = 10  # 5 minutes
CACHE_TIMEOUT_FOR_TRUST_LINE = 300  # 5 minutes
CACHE_TIMEOUT_FOR_WALLET = 300  # Cache timeout in seconds (e.g., 5 minutes)
CACHE_TIMEOUT_FOR_TRANSACTION_HISTORY = 300  # Cache timeout in seconds (e.g., 5 minutes)

# XRPL-specific constraints
MAX_DID_DOCUMENT_SIZE = 1024  # Approximate practical limit in bytes for DIDDocument field
MAX_URI_SIZE = 256  # Max bytes for URI field

asfDisableMaster = 1114112

BASE_RESERVE = 2  # Base reserve in XRP; update if it changes

# Constants for text
ENTERING_FUNCTION_LOG = "Entering: {}"
LEAVING_FUNCTION_LOG = "Leaving: {}. Total execution time in ms: {}"
ERROR_INITIALIZING_CLIENT = "Failed to initialize XRPL client. Client returned None"
ERROR_CREATING_TEST_WALLET = 'Error creating new wallet. generate_faucet_wallet returned None.'
ERROR_INITIALIZING_SERVER_INFO = "Error initializing ledger info."
ERROR_CREATING_ACCOUNT_INFO_OBJECT = "Error creating Account Info object."
ERROR_GETTING_ACCOUNT_INFO = "Error getting Account information."
INVALID_XRP_BALANCE = "Invalid XRP balance. Balance is either None or not greater than zero"
FAILED_TO_FETCH_RESERVE_DATA = 'Failed to fetch reserve data for account {}.'
ERROR = 'error'
STATUS = 'status'
FAILURE = 'failure'
MESSAGE = 'message'
CLASSIC_XRP_ADDRESS = 'Classic address:'
X_XRP_ADDRESS = 'X-address:'
XRPL_RESPONSE = "Raw XRPL response:"
SENDER_SEED_IS_INVALID = 'Sender seed is invalid.'
INSUFFICIENT_BALANCE_TO_COVER_RESERVER_FEES = 'Insufficient balance to cover the reserve and fees.'
ERROR_IN_XRPL_RESPONSE = "Error in response from XRPL client."
ERROR_FETCHING_TRANSACTION_HISTORY = "Error fetching transaction history info."
ERROR_FETCHING_TRANSACTION_STATUS = 'Error while checking transaction status.'
ERROR_FETCHING_ACCOUNT_OFFERS = 'Error while fetching account offers.'
ERROR_FETCHING_XRP_RESERVES = 'Error while fetching XRP reserves.'
INVALID_WALLET_IN_REQUEST = 'Invalid wallet format passed in request.'
INVALID_TX_ID_IN_REQUEST = 'Invalid transaction id passed in request.'
RESERVES_NOT_FOUND = 'Reserves not found.'
ACCOUNT_IS_REQUIRED = 'Account address is required.'
INVALID_TRANSACTION_HASH = 'Invalid transaction hash.'
PAYMENT_IS_UNSUCCESSFUL = "Payment response is unsuccessful"
MISSING_REQUEST_PARAMETERS = "Missing required parameters."
UNABLE_TO_FETCH_ACCOUNT_OFFERS = "Unable to fetch account offers for cancellation"
NO_OFFER_TO_CANCEL_FOR_THIS_ACCOUNT = "No offers available to cancel"
ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER = "Account {} does not exist on the ledger or it has been deleted."

ASF_FLAGS = [
    'asf_account_txn_id',
    'asf_allow_trustline_clawback',
    'asf_authorized_nftoken_minter',
    'asf_default_ripple',
    'asf_deposit_auth',
    'asf_disable_master',
    'asf_disable_incoming_check',
    'asf_disable_incoming_nftoken_offer',
    'asf_disable_incoming_paychan',
    'asf_disable_incoming_trustline',
    'asf_disallow_XRP',
    'asf_global_freeze',
    'asf_no_freeze',
    'asf_require_auth',
    'asf_require_dest'
]

# Mapping of flag names to database column names
ASF_FLAG_MAPPING = {
    'asf_account_txn_id': 'ASF_ACCOUNT_TXN_ID',
    'asf_allow_trustline_clawback': 'ASF_ALLOW_TRUSTLINE_CLAWBACK',
    'asf_authorized_nftoken_minter': 'ASF_AUTHORIZED_NFTOKEN_MINTER',
    'asf_default_ripple': 'ASF_DEFAULT_RIPPLE',
    'asf_deposit_auth': 'ASF_DEPOSIT_AUTH',
    'asf_disable_master': 'ASF_DISABLE_MASTER',
    'asf_disable_incoming_check': 'ASF_DISABLE_INCOMING_CHECK',
    'asf_disable_incoming_nftoken_offer': 'ASF_DISABLE_INCOMING_NFTOKEN_OFFER',
    'asf_disable_incoming_paychan': 'ASF_DISABLE_INCOMING_PAYCHAN',
    'asf_disable_incoming_trustline': 'ASF_DISABLE_INCOMING_TRUSTLINE',
    'asf_disallow_xrp': 'ASF_DISALLOW_XRP',
    'asf_global_freeze': 'ASF_GLOBAL_FREEZE',
    'asf_no_freeze': 'ASF_NO_FREEZE',
    'asf_require_auth': 'ASF_REQUIRE_AUTH',
    'asf_require_dest': 'ASF_REQUIRE_DEST'
}

ASF_FLAG_MAPPINGS = {
    'asf_account_txn_id': 'ASF_ACCOUNT_TXN_ID',
    'allowTrustLineClawback': 'ASF_ALLOW_TRUSTLINE_CLAWBACK',
    'asf_authorized_nftoken_minter': 'ASF_AUTHORIZED_NFTOKEN_MINTER',
    'defaultRipple': 'ASF_DEFAULT_RIPPLE',
    'depositAuth': 'ASF_DEPOSIT_AUTH',
    'disableMasterKey': 'ASF_DISABLE_MASTER',
    'disallowIncomingCheck': 'ASF_DISABLE_INCOMING_CHECK',
    'disallowIncomingNFTokenOffer': 'ASF_DISABLE_INCOMING_NFTOKEN_OFFER',
    'disallowIncomingPayChan': 'ASF_DISABLE_INCOMING_PAYCHAN',
    'disallowIncomingTrustline': 'ASF_DISABLE_INCOMING_TRUSTLINE',
    'disallowIncomingXRP': 'ASF_DISALLOW_XRP',
    'globalFreeze': 'ASF_GLOBAL_FREEZE',
    'noFreeze': 'ASF_NO_FREEZE',
    'requireAuthorization': 'ASF_REQUIRE_AUTH',
    'requireDestinationTag': 'ASF_REQUIRE_DEST'
}

# Filter for specific types
ACCOUNT_OBJECTS_TYPE = ["escrow", "offer", "payment_channel", "paychan", "ripple_state", "state", "check",
                           "ticket", "nftoken_page", "deposit_preauth", "signer_list","amm", "did"]

MINT_NFT_TX_FLAG_OPTIONS = ['TF_TRANSFERABLE','TF_BURNABLE','TF_ONLY_XRP', 'TRANSFER_AND_BURNABLE',
                            'TRANSFER_AND_XRP', 'BURNABLE_AND_XRP']

DID_SCHEMA = {
    "type": "object",
    "required": ["@context", "id"],
    "properties": {
        "@context": {
            "type": ["string", "array"],
            "items": {"type": "string"},
            "contains": {"const": "https://www.w3.org/ns/did/v1"}
        },
        "id": {
            "type": "string",
            "pattern": "^did:xrpl:1:[a-fA-F0-9]{66}$"  # XRPL DID format: 33-byte pubkey (66 hex chars)
        },
        "verificationMethod": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "type", "controller", "publicKeyMultibase"],
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "controller": {"type": "string", "pattern": "^did:xrpl:1:[a-fA-F0-9]{66}$"},
                    "publicKeyMultibase": {"type": "string"}
                }
            }
        },
        "service": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "type", "serviceEndpoint"],
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "serviceEndpoint": {"type": ["string", "object"]}
                }
            }
        }
    },
    "additionalProperties": True
}