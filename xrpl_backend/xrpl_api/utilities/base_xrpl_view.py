# Base class with shared functionality
import logging
import re

from django.views import View
from xrpl import XRPLException
from xrpl.core.addresscodec import is_valid_classic_address, is_valid_xaddress
from xrpl.core.keypairs import derive_keypair, derive_classic_address
from xrpl.utils import xrp_to_drops, XRPRangeException

from ..errors.error_handling import error_response
from ..utilities.utilities import get_xrpl_client

logger = logging.getLogger('xrpl_app')


class BaseXRPLView(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def _initialize_client(self):
        """Lazy initialization of the XRPL client and utils."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response("Error initializing XRPL client"))

    @staticmethod
    def _is_valid_xrpl_seed(seed: str) -> bool:
        """
        Validates an XRP Ledger (XRPL) seed.

        A valid XRPL seed must be able to derive a keypair, from which a classic address can be derived,
        and that address must be valid according to the XRPL's rules.

        Args:
            seed (str): The XRPL seed to validate.

        Returns:
            bool: True if the seed is valid, False otherwise.
        """
        try:
            # Attempt to derive a keypair from the seed. If this fails, the seed is invalid.
            public_key, _ = derive_keypair(seed)

            # Derive a classic address from the derived public key.
            classic_address = derive_classic_address(public_key)

            # Validate the resulting classic address according to XRPL rules.
            return is_valid_classic_address(classic_address)

        except XRPLException:
            return False  # The seed was invalid, an exception was raised during the derivation process.

    @staticmethod
    def _validate_xrp_wallet(address: str) -> bool:
        """
        Validates whether the provided address is a valid XRP wallet address.

        This function checks if the address is either a valid classic XRP address
        or a valid X-Address format. If the address is valid, it logs the type of
        address and returns True. If the address is invalid, it logs an error and
        returns False.

        Args:
            address (str): The XRP wallet address to validate.

        Returns:
            bool: True if the address is valid (classic or X-Address), False otherwise.
        """
        if is_valid_classic_address(address):
            logger.info(f"Classic Address: {address}")
            return True
        elif is_valid_xaddress(address):
            logger.info(f"X-Address: {address}")
            return True
        else:
            logger.error(f"Invalid Address: {address}")
            return False

    @staticmethod
    def _is_valid_xrp_amount(amount: str) -> bool:
        try:
            xrp_to_drops(float(amount))  # This will raise an error if the amount is invalid
            print(f"xrp_to_drops(float(amount)): {xrp_to_drops(float(amount))}")
            return True
        except XRPRangeException:
            return False

    @staticmethod
    def _is_valid_currency_amount(amount: str, currency_code: str) -> bool:
        """Validates issued currency amounts (up to 15 decimal places)."""
        try:
            if not BaseXRPLView._is_valid_amount(amount):
                return False
            if not re.match(r"^\d+(\.\d{1,15})?$", amount):  # Up to 15 decimal places
                return False
            return BaseXRPLView._is_valid_currency_code(currency_code)  # Check if the currency code is valid
        except ValueError:
            return False

    @staticmethod
    def _is_valid_currency_code(currency_code: str) -> bool:
        """Validates XRPL issued currency codes (ISO 4217 or 160-bit hex)."""
        return bool(re.match(r"^[A-Z0-9]{3}$", currency_code) or re.match(r"^[A-Fa-f0-9]{40}$", currency_code))

    @staticmethod
    def _is_valid_amount(amount):
        value = float(amount)
        if value <= 0:
            return False

        return True
