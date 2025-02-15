from django.apps import AppConfig
from django.conf import settings
import logging

logger = logging.getLogger('xrpl_app')

class XrplApiConfig(AppConfig):
    name = 'xrpl_api'
    JSON_RPC_URL = None  # Initialize as None
    XRP_FAUCET_URL = None  # Initialize as None
    # Initialize as 10. This is only if there is a problem reading the value from the .env file
    XRP_ACCOUNT_DELETE_FEE_IN_DROPS = 10
    # Initialize as 10. This is only if there is a problem reading the value from the .env file
    XRP_SEND_ACCOUNT_FEE_IN_DROPS = 10 # Initialize as 10

    logger.info("----------------- App started ----------------- ")

    def ready(self):
        # Set JSON_RPC_URL and XRP_FAUCET_URL when the app is ready
        xrpl_network = settings.XRP_NETWORK
        if xrpl_network == 'testnet':
            self.JSON_RPC_URL = settings.XRPL_TEST_NETWORK_URL
            self.XRP_FAUCET_URL = settings.XRP_FAUCET_URL
        elif xrpl_network == 'devnet':
            self.JSON_RPC_URL = settings.XRPL_DEV_NETWORK_URL
            self.XRP_FAUCET_URL = settings.XRP_FAUCET_URL
        elif xrpl_network == 'prodnet':
            self.JSON_RPC_URL = settings.XRPL_PROD_NETWORK_URL
            self.XRP_FAUCET_URL = ''
        else:
            self.JSON_RPC_URL = ''
            self.XRP_FAUCET_URL = ''

        self.XRP_ACCOUNT_DELETE_FEE_IN_DROPS = settings.XRP_ACCOUNT_DELETE_FEE_IN_DROPS
        self.XRP_SEND_ACCOUNT_FEE_IN_DROPS = settings.XRP_SEND_ACCOUNT_FEE_IN_DROPS

        logger.info(f"Using XRP URL: {self.JSON_RPC_URL}")
        logger.info(f"Using XRP FAUCET URL: {self.XRP_FAUCET_URL}")
        logger.info(f"XRP_ACCOUNT_DELETE_FEE_IN_DROPS: {self.XRP_ACCOUNT_DELETE_FEE_IN_DROPS}")
        logger.info(f"XRP_SEND_ACCOUNT_FEE_IN_DROPS: {self.XRP_SEND_ACCOUNT_FEE_IN_DROPS}")
