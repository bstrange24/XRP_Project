from xrpl.models import ServerInfo
import logging

from ..utils import get_xrpl_client

logger = logging.getLogger('xrpl_app')

def get_account_reserves():
    """
    Fetches the current reserve requirements from the XRP Ledger.

    This function queries the XRP Ledger server to retrieve the base reserve
    and reserve increment values, which are required for account operations.
    It handles errors gracefully and logs appropriate messages for debugging.

    Returns:
        tuple: A tuple containing (base_reserve, reserve_inc) as integers.
               If the data is unavailable or an error occurs, returns (None, None).

    Example:
        base_reserve, reserve_inc = get_account_reserves()
        if base_reserve and reserve_inc:
            print(f"Base Reserve: {base_reserve}, Reserve Increment: {reserve_inc}")
    """
    try:
        # Request server info from the XRP Ledger using the XRPL client
        response = get_xrpl_client().request(ServerInfo())

        # Extract the 'validated_ledger' object from the server info response
        validated_ledger = response.result.get('info', {}).get('validated_ledger', {})

        # Retrieve the base reserve and reserve increment values from the validated ledger
        base_reserve = validated_ledger.get('reserve_base_xrp')
        reserve_inc = validated_ledger.get('reserve_inc_xrp')

        # Check if either value is missing (None)
        if base_reserve is None or reserve_inc is None:
            logger.error("Reserve data not found in server info.")
            return None, None

        # Convert the values to integers and return them
        return int(base_reserve), int(reserve_inc)

    except Exception as e:
        # Log any exceptions that occur during the process
        logger.error(f"Error fetching server info: {e}")
        return None, None