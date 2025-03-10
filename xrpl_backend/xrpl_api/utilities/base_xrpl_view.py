# Base class with shared functionality
from django.http import JsonResponse
from django.views import View
from xrpl import XRPLException

from ..errors.error_handling import error_response
from ..utilities.utilities import get_xrpl_client


class BaseXRPLView(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client
        self.utils = None

    def _initialize_client(self):
        """Lazy initialization of the XRPL client and utils."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response("Error initializing XRPL client"))

    def _send_response(self, success=True, data=None, error=None):
        """Helper to format JSON response."""
        response = {"success": success}
        if data:
            response["data"] = data
        if error:
            response["error"] = error
        return JsonResponse(response)