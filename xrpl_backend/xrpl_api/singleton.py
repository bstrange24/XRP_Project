# xrpl_api/singleton.py
import logging

logger = logging.getLogger('xrpl_app')

class XrplConfigSingleton:
    _instance = None
    JSON_RPC_URL = None
    XRP_FAUCET_URL = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def initialize(self, settings):
        if not self.initialized:
            self.initialized = True

            # Set JSON_RPC_URL and XRP_FAUCET_URL
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

            logger.info(f"Using XRP URL: {self.JSON_RPC_URL}")
            logger.info(f"Using XRP FAUCET URL: {self.XRP_FAUCET_URL}")