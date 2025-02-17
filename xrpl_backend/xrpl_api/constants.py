import logging

logger = logging.getLogger('xrpl_app')

# Constants for flags
REQUIRE_DESTINATION_TAG_FLAG = 0x00010000  # 0x00010000: Require Destination Tag
DISABLE_MASTER_KEY_FLAG = 0x00040000  # 0x00040000: Disable Master Key
ENABLE_REGULAR_KEY_FLAG = 0x00080000  # 0x00080000: Enable Regular Key
MAX_RETRIES = 3  # Maximum retry attempts
RETRY_BACKOFF = 2  # Exponential backoff base in seconds

PAGINATION_PAGE_SIZE = 10

CACHE_TIMEOUT = 60  # 1 minute cache timeout
CACHE_TIMEOUT_FOR_TRUST_LINES = 300
CACHE_TIMEOUT_FOR_GET_OFFERS = 10  # 10 seconds
CACHE_TIMEOUT_FOR_SERVER_INFO = 300  # 5 minutes
CACHE_TIMEOUT_FOR_TRUST_LINE = 300  # 5 minutes
CACHE_TIMEOUT_FOR_WALLET = 300  # Cache timeout in seconds (e.g., 5 minutes)
CACHE_TIMEOUT_FOR_TRANSACTION_HISTORY = 300  # Cache timeout in seconds (e.g., 5 minutes)

asfDisableMaster = 1114112

BASE_RESERVE = 2  # Base reserve in XRP; update if it changes

# Constants for text
ENTERING_FUNCTION_LOG = "Entering: {}"
LEAVING_FUNCTION_LOG = "Leaving: {}. Total execution time in ms: {}"
ERROR_INITIALIZING_CLIENT = "Failed to initialize XRPL client."
ERROR_INITIALIZING_SERVER_INFO = "Error initializing ledger info."
ERROR_CREATING_ACCOUNT_INFO_OBJECT = "Error creating Account Info object."
ERROR_GETTING_ACCOUNT_INFO = "Error getting Account information."
XRPL_RESPONSE = "Raw XRPL response:"
ERROR_IN_XRPL_RESPONSE = "Error in response from XRPL client."
ERROR_FETCHING_TRANSACTION_HISTORY = "Error fetching transaction history info."
ERROR_FETCHING_TRANSACTION_STATUS = 'Error while checking transaction status.'
ERROR_FETCHING_ACCOUNT_OFFERS = 'Error while fetching account offers.'
ERROR_FETCHING_XRP_RESERVES = 'Error while fetching XRP reserves.'
INVALID_WALLET_IN_REQUEST = 'Invalid wallet format passed in request.'
RESERVES_NOT_FOUND = 'Reserves not found.'
ACCOUNT_IS_REQUIRED = 'Account address is required.'
INVALID_TRANSACTION_HASH = 'Invalid transaction hash.'
PAYMENT_IS_UNSUCCESSFUL = "Payment response is unsuccessful"
MISSING_REQUEST_PARAMETERS = "Missing required parameters."