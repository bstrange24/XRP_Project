import logging

logger = logging.getLogger('xrpl_app')

# Constants for flags
# DEFAULT_RIPPLE_FLAG = 0x00010000 # (default_ripple) The account will allow for rippling by default.
# DEPOSIT_AUTH_FLAG = 0x00000100 # (deposit_auth) Description: This flag restricts deposits to an account, meaning that the account will only accept deposits from authorized sources. When this flag is set, deposits will be accepted only if the transaction is coming from an account that is explicitly authorized by the account owner.
# DISABLE_MASTER_KEY_FLAG = 0x00040000 # (disable_master_key) Disables the use of the master key for the account. This is useful if the account uses a regular key.
# DISALLOW_INCOMING_CHECK_FLAG = 0x00000200 # (disallow_incoming_check) Description: This flag prevents incoming transactions from passing the "check" validation when trying to send XRP to the account. This flag essentially makes it impossible for the account to be used as a destination for certain types of transactions
# DISALLOW_INCOMING_NFTOKEN_OFFER_FLAG = 0x00010000 # (disallow_incoming_NFToken_offer) Description: This flag prevents the account from accepting incoming offers for NFTokens (Non-Fungible Tokens). This flag is useful for accounts that do not want to participate in receiving or accepting offers for NFTs.
# DISALLOW_INCOMING_PAYCHAN_FLAG = 0x00020000 # (disallow_incoming_pay_chan) Description: This flag prevents the account from accepting incoming payments through payment channels. Payment channels are a way of making multiple payments between two parties off the XRP ledger, and this flag disables the ability for an account to accept payments via this mechanism
# DISALLOW_INCOMING_TRUSTLINE_FLAG = 0x00040000 # (disallow_incoming_trust_line) Description: This flag prevents an account from accepting new trust lines (i.e., the ability for other accounts to trust the account's issued tokens or currencies). When this flag is enabled, the account will not allow other accounts to establish trust lines with it for issuing tokens or holding the account's assets.
# DISALLOW_INCOMING_XRP_FLAG = 0x00000040 # (disallow_incoming_XRP) Description: This flag prevents the account from accepting incoming XRP. This means that other accounts cannot send XRP to this account.
# GLOBAL_FREEZE_FLAG = 0x00010000 # (global_freeze) Description: The account has been frozen globally, meaning the account cannot send XRP, and no other account can transfer XRP to it.
# NO_FREEZE_FLAG = 0x00020000 # (no_freeze) Description: When set, the account cannot be frozen by other accounts
# PASSWORD_SPENT_FLAG = 0x00040000 # (password_spent) Description: The account's password (or master key) has been used to create a new key pair.
# REQUIRE_AUTHORIZATION_FLAG = 0x00080000 # (require_authorization) Description: This flag indicates that transactions from this account require explicit authorization from a third party or some external authorization mechanism.
# REQUIRE_DESTINATION_TAG_FLAG = 0x00010000 # (require_destination_tag) Description: This flag requires a destination tag for transactions involving the account.
# ENABLE_REGULAR_KEY_FLAG = 0x00080000 # (enable_regular_key_flag) Description: Enables the regular key for the account (i.e., it allows the regular key to sign transactions instead of the master key).
# ALLOW_TRUSTLINE_CLAWBACK_FLAG = 0x00100000 # (allow_trust_line_clawback_flag) Description: When this flag is set, the account can revoke (clawback) trust lines by sending a TrustSet transaction to the network with a clawback action on a trust line. This can prevent certain users from using trust lines or tokens associated with the issuer.
# ALLOW_RIPPLE_FLAG = 0x02000000 # (allow_ripple_flag) Description: Allows the account to ripples with other accounts (this is the "ripple" flag). Accounts with this flag set can have their XRP balances sent to other accounts via rippling.
# DISABLE_TRANSACTION_SIGS_FLAG = 0x04000000 # (disable_transaction_sig_flag) Description: Disables the account from signing transactions.
# THIRD_PARTY_AUTH_FLAG = 0x08000000 # (third_party_auth_flag) Description: Account requires third-party authorization to send funds.
# SINGLE_SIGNER_FLAG = 0x10000000 # (single_signer_flag) Description: Only one signer is needed for transactions from this account (used in multi-sig contexts).
# DEACTIVATE_FLAG = 0x20000000 # (deactivate_flag) Description: This flag deactivates the account (the account no longer can send XRP). Typically used when you want to lock an account.
# DISABLE_AUTHENTICATION_FLAG = 0x40000000 # (disable_authentication_flag) Description: Account has disabled its ability to use authentication.
# DISABLE_MULTISIG_FLAG = 0x00000040 # (disable_multisig_flag) Description: Prevents the use of multi-signature accounts.
# ALLOW_PARTIAL_PAYMENT_FLAG = 0x00000080 # (allow_partial_payment_flag) Description: Allows the use of partial payments in transactions.
# SET_ISSUER_TAG_FLAG =0x00000001 # (set_issuer_tag_flag) Description: Set the issuer tag for an account


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
ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER = "Account does not exist on the ledger."