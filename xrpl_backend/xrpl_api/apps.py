from django.apps import AppConfig
from django.conf import settings
import logging

logger = logging.getLogger('xrpl_app')

class XrplApiConfig(AppConfig):
    name = 'xrpl_api'
    JSON_RPC_URL = None  # Initialize as None
    XRP_FAUCET_URL = None
    XRPL_WEB_SOCKET_NETWORK_URL = None
    XRPL_CLIO_NETWORK_URL = None
    XRPL_CLIO_WEB_SOCKET_NETWORK_URL = None
    XRPL_LABS_NETWORK_URL = None
    XRPL_CLIO_LABS_WEB_SOCKET_NETWORK_URL = None
    ESCROW_DEFAULT_CLAIM_AFTER_DATE = None
    ESCROW_DEFAULT_FINISH_AFTER_DATE = None

    # Initialize as 10. This is only if there is a problem reading the value from the .env file
    XRP_ACCOUNT_DELETE_FEE_IN_DROPS = 10
    # Initialize as 10. This is only if there is a problem readin
    # g the value from the .env file
    XRP_SEND_ACCOUNT_FEE_IN_DROPS = 10 # Initialize as 10
    BLACK_HOLE_ADDRESS = None

    logger.info("----------------- App started ----------------- ")

    def ready(self):
        xrpl_network = settings.XRP_NETWORK
        logger.info(f"Environment: {xrpl_network}")

        if xrpl_network == 'devnet':
            self.JSON_RPC_URL = settings.XRPL_DEV_NETWORK_URL
            self.XRP_FAUCET_URL = settings.XRP_DEV_FAUCET_URL
            self.XRPL_WEB_SOCKET_NETWORK_URL = settings.XRPL_DEV_WEB_SOCKET_NETWORK_URL
            self.XRPL_CLIO_NETWORK_URL = settings.XRPL_DEV_CLIO_NETWORK_URL
            self.XRPL_CLIO_WEB_SOCKET_NETWORK_URL = settings.XRPL_DEV_CLIO_WEB_SOCKET_NETWORK_URL
            self.ESCROW_DEFAULT_CLAIM_AFTER_DATE = settings.ESCROW_DEV_DEFAULT_CLAIM_AFTER_DATE
            self.ESCROW_DEFAULT_FINISH_AFTER_DATE = settings.ESCROW_DEV_DEFAULT_FINISH_AFTER_DATE
        elif xrpl_network == 'testnet':
            self.JSON_RPC_URL = settings.XRPL_TEST_NETWORK_URL
            self.XRP_FAUCET_URL = settings.XRP_TEST_FAUCET_URL
            self.XRPL_WEB_SOCKET_NETWORK_URL = settings.XRPL_TEST_WEB_SOCKET_NETWORK_URL
            self.XRPL_LABS_NETWORK_URL = settings.XRPL_TEST_LABS_NETWORK_URL
            self.XRPL_CLIO_LABS_WEB_SOCKET_NETWORK_URL = settings.XRPL_TEST_LABS_WEB_SOCKET_NETWORK_URL
            self.XRPL_CLIO_NETWORK_URL = settings.XRPL_TEST_CLIO_NETWORK_URL
            self.XRPL_CLIO_WEB_SOCKET_NETWORK_URL = settings.XRPL_TEST_CLIO_WEB_SOCKET_NETWORK_URL
            self.ESCROW_DEFAULT_CLAIM_AFTER_DATE = settings.ESCROW_TEST_DEFAULT_CLAIM_AFTER_DATE
            self.ESCROW_DEFAULT_FINISH_AFTER_DATE = settings.ESCROW_TEST_DEFAULT_FINISH_AFTER_DATE
        elif xrpl_network == 'prodnet':
            self.JSON_RPC_URL = settings.XRPL_PROD_NETWORK_URL
            self.XRP_FAUCET_URL = settings.XRP_PROD_FAUCET_URL
            self.XRPL_WEB_SOCKET_NETWORK_URL = settings.XRPL_PROD_WEB_SOCKET_NETWORK_URL
            self.ESCROW_DEFAULT_CLAIM_AFTER_DATE = settings.ESCROW_PROD_DEFAULT_CLAIM_AFTER_DATE
            self.ESCROW_DEFAULT_FINISH_AFTER_DATE = settings.ESCROW_PROD_DEFAULT_FINISH_AFTER_DATE

        self.XRP_ACCOUNT_DELETE_FEE_IN_DROPS = settings.XRP_ACCOUNT_DELETE_FEE_IN_DROPS
        self.XRP_SEND_ACCOUNT_FEE_IN_DROPS = settings.XRP_SEND_ACCOUNT_FEE_IN_DROPS
        self.BLACK_HOLE_ADDRESS = settings.BLACK_HOLE_ADDRESS

        logger.info(f"Using XRP URL: {self.JSON_RPC_URL}")
        logger.info(f"Using XRP FAUCET URL: {self.XRP_FAUCET_URL}")
        logger.info(f"Using XRP WEB SOCKET URL: {self.XRPL_WEB_SOCKET_NETWORK_URL}")
        logger.info(f"Using XRPL TEST LABS NETWORK URL: {self.XRPL_LABS_NETWORK_URL}")
        logger.info(f"Using XRPL TEST LABS WEB SOCKET NETWORK URL: {self.XRPL_CLIO_LABS_WEB_SOCKET_NETWORK_URL}")
        logger.info(f"Using XRPL TEST CLIO NETWORK URL: {self.XRPL_CLIO_NETWORK_URL}")
        logger.info(f"Using XRPL TEST CLIO WEB SOCKET NETWORK URL: {self.XRPL_CLIO_WEB_SOCKET_NETWORK_URL}")
        logger.info(f"XRP_ACCOUNT_DELETE_FEE_IN_DROPS: {self.XRP_ACCOUNT_DELETE_FEE_IN_DROPS}")
        logger.info(f"XRP_SEND_ACCOUNT_FEE_IN_DROPS: {self.XRP_SEND_ACCOUNT_FEE_IN_DROPS}")
        logger.info(f"BLACK_HOLE_ADDRESS: {self.BLACK_HOLE_ADDRESS}")
        logger.info(f"ESCROW_DEFAULT_FINISH_AFTER_DATE: {self.ESCROW_DEFAULT_FINISH_AFTER_DATE}")
        logger.info(f"ESCROW_DEFAULT_CLAIM_AFTER_DATE: {self.ESCROW_DEFAULT_CLAIM_AFTER_DATE}")
