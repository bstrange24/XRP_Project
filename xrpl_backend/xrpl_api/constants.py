FAUCET_URL = "https://faucet.altnet.rippletest.net/accounts"
JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/"

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

BASE_RESERVE = 2  # Base reserve in XRP; update if it changes

# Constants for text
ERROR_INITIALIZING_CLIENT = "Error initializing client."
ERROR_CREATING_ACCOUNT_INFO_OBJECT = "Error creating Account Info object."
XRPL_RESPONSE = "Raw XRPL response:"
ERROR_IN_XRPL_RESPONSE = "Error in response from XRPL client"
INVALID_WALLET_IN_REQUEST = 'Invalid wallet format passed in request.'
ACCOUNT_IS_REQUIRED = 'Account address is required.'
