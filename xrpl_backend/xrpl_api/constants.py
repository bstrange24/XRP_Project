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
CACHE_TIMEOUT_FOR_GET_OFFERS = 300  # 5 minutes
CACHE_TIMEOUT_FOR_SERVER_INFO = 300  # 5 minutes
CACHE_TIMEOUT_FOR_TRUST_LINE = 300  # 5 minutes