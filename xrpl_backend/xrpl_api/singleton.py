# xrpl_api/singleton.py
import logging

logger = logging.getLogger('xrpl_app')

class XrplConfigSingleton:
    _instance = None
    JSON_RPC_URL = None
    XRP_FAUCET_URL = None
    XRPL_WEB_SOCKET_NETWORK_URL = None
    XRPL_CLIO_NETWORK_URL = None
    XRPL_CLIO_WEB_SOCKET_NETWORK_URL = None
    XRPL_LABS_NETWORK_URL = None
    XRPL_CLIO_LABS_WEB_SOCKET_NETWORK_URL = None
    XRP_ACCOUNT_DELETE_FEE_IN_DROPS = 10
    XRP_SEND_ACCOUNT_FEE_IN_DROPS = 10
    BLACK_HOLE_ADDRESS = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def initialize(self, settings):
        if not self.initialized:
            self.initialized = True

            # Set JSON_RPC_URL and XRP_TEST_FAUCET_URL
            xrpl_network = settings.XRP_NETWORK
            if xrpl_network == 'devnet':
                self.JSON_RPC_URL = settings.XRPL_DEV_NETWORK_URL
                self.XRP_FAUCET_URL = settings.XRP_DEV_FAUCET_URL
                self.XRPL_WEB_SOCKET_NETWORK_URL = settings.XRPL_DEV_WEB_SOCKET_NETWORK_URL
                self.XRPL_CLIO_NETWORK_URL = settings.XRPL_DEV_CLIO_NETWORK_URL
                self.XRPL_CLIO_WEB_SOCKET_NETWORK_URL = settings.XRPL_DEV_CLIO_WEB_SOCKET_NETWORK_URL
            elif xrpl_network == 'testnet':
                self.JSON_RPC_URL = settings.XRPL_TEST_NETWORK_URL
                self.XRP_FAUCET_URL = settings.XRP_TEST_FAUCET_URL
                self.XRPL_WEB_SOCKET_NETWORK_URL = settings.XRPL_TEST_WEB_SOCKET_NETWORK_URL
                self.XRPL_LABS_NETWORK_URL = settings.XRPL_TEST_LABS_NETWORK_URL
                self.XRPL_CLIO_LABS_WEB_SOCKET_NETWORK_URL = settings.XRPL_TEST_LABS_WEB_SOCKET_NETWORK_URL
                self.XRPL_CLIO_NETWORK_URL = settings.XRPL_TEST_CLIO_NETWORK_URL
                self.XRPL_CLIO_WEB_SOCKET_NETWORK_URL = settings.XRPL_TEST_CLIO_WEB_SOCKET_NETWORK_URL
            elif xrpl_network == 'prodnet':
                self.JSON_RPC_URL = settings.XRPL_PROD_NETWORK_URL
                self.XRP_FAUCET_URL = settings.XRP_PROD_FAUCET_URL
                self.XRPL_WEB_SOCKET_NETWORK_URL = settings.XRPL_PROD_WEB_SOCKET_NETWORK_URL

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