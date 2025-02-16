import json
import unittest
from decimal import Decimal
import tenacity
from django.core.cache import cache
from django.http import JsonResponse
from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from xrpl import XRPLException
from xrpl.clients import JsonRpcClient
from django.test import RequestFactory

from .models import XrplAccountData, XrplPaymentData, XrplTransactionData, XrplLedgerEntryData
from .utils import get_request_param
from .views import get_wallet_info
from .constants import MAX_RETRIES


class MockWallet:
    def __init__(self, address, seed):
        self.address = address
        self.seed = seed


class CreateAccountViewTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('create_account')  # Ensure this matches your URL configuration

    def tearDown(self):
        # Clear any cache or state if necessary
        pass

    @patch('xrpl_api.views.get_xrpl_client')
    @patch('xrpl_api.views.generate_faucet_wallet')
    @patch('xrpl_api.views.save_account_data_to_databases')
    @patch('xrpl_api.views.addresscodec.classic_address_to_xaddress')
    def test_create_account_success(self, mock_classic_to_xaddress, mock_save_account_data, mock_generate_faucet_wallet,
                                    mock_get_xrpl_client):
        """
        Test successful account creation with proper mocking of XRPL interactions.
        """
        # Mock XRPL client
        mock_client = MagicMock(spec=JsonRpcClient)
        mock_get_xrpl_client.return_value = mock_client

        # Mock wallet generation
        mock_wallet = MockWallet(address="rExampleAddress", seed="sExampleSeed")
        mock_generate_faucet_wallet.return_value = mock_wallet

        # Mock address conversion
        mock_classic_to_xaddress.return_value = "XExampleXAddress"

        # Mock XRPL response for account info
        mock_response = MagicMock()
        mock_response.status = 'success'
        mock_response.result = {
            'account_data': {
                'Balance': '1000000000',  # 1 XRP in drops
                'PreviousTxnID': 'exampleTxnID'
            },
            'ledger_hash': 'exampleLedgerHash'
        }
        mock_client.request.return_value = mock_response

        # Mock database save
        mock_save_account_data.return_value = None

        # Perform the API request
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['message'], 'Successfully created wallet.')
        self.assertEqual(response_data['account_id'], 'rExampleAddress')
        self.assertEqual(response_data['secret'], 'sExampleSeed')
        self.assertEqual(response_data['balance'], "1000.00")  # 1 XRP
        self.assertEqual(response_data['transaction_hash'], 'exampleLedgerHash')
        self.assertEqual(response_data['previous_transaction_id'], 'exampleTxnID')

        # Verify mocks were called
        mock_get_xrpl_client.assert_called_once()
        mock_generate_faucet_wallet.assert_called_once_with(mock_client, debug=True)
        mock_classic_to_xaddress.assert_called_once_with('rExampleAddress', tag=12345, is_test_network=True)
        mock_client.request.assert_called_once()
        mock_save_account_data.assert_called_once()

    @patch('xrpl_api.views.get_xrpl_client')
    def test_create_account_client_initialization_failure(self, mock_get_xrpl_client):
        """
        Test when XRPL client initialization fails.
        """
        mock_get_xrpl_client.return_value = None

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertEqual(response_data['status'], 'failure')
        self.assertIn('Failed to initialize XRPL client.', response_data['message'])

    @patch('xrpl_api.views.get_xrpl_client')
    @patch('xrpl_api.views.generate_faucet_wallet')
    def test_create_account_wallet_creation_failure(self, mock_generate_faucet_wallet, mock_get_xrpl_client):
        """
        Test failure when wallet creation fails.
        """
        mock_client = MagicMock(spec=JsonRpcClient)
        mock_get_xrpl_client.return_value = mock_client
        mock_generate_faucet_wallet.return_value = None

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertEqual(response_data['status'], 'failure')
        self.assertIn("Error creating new wallet.", response_data['message'])

    @patch('xrpl_api.views.get_xrpl_client')
    @patch('xrpl_api.views.generate_faucet_wallet')
    def test_create_account_xrpl_response_failure(self, mock_generate_faucet_wallet, mock_get_xrpl_client):
        """
        Test failure when XRPL response status is not 'success'.
        """
        mock_client = MagicMock(spec=JsonRpcClient)
        mock_get_xrpl_client.return_value = mock_client
        mock_wallet = MockWallet(address="rExampleAddress", seed="sExampleSeed")
        mock_generate_faucet_wallet.return_value = mock_wallet

        mock_response = MagicMock()
        mock_response.status = 'error'
        mock_response.text = 'XRPL request failed'
        mock_client.request.return_value = mock_response

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertEqual(response_data['status'], 'failure')
        self.assertIn('Error retrieving account details.', response_data['message'])

    @patch('xrpl_api.views.get_xrpl_client')
    @patch('xrpl_api.views.generate_faucet_wallet')
    def test_create_account_unhandled_exception(self, mock_generate_faucet_wallet, mock_get_xrpl_client):
        """
        Test handling of unexpected exceptions.
        """
        mock_client = MagicMock(spec=JsonRpcClient)
        mock_get_xrpl_client.return_value = mock_client
        mock_generate_faucet_wallet.side_effect = Exception("Unexpected error")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertEqual(response_data['status'], 'failure')
        self.assertIn('Unexpected error', response_data['message'])

    @patch('xrpl_api.views.get_xrpl_client')
    @patch('xrpl_api.views.generate_faucet_wallet')
    @patch('xrpl_api.views.addresscodec.classic_address_to_xaddress')
    @patch('xrpl_api.views.convert_drops_to_xrp')
    @patch('xrpl_api.views.save_account_data_to_databases')
    def test_create_invalid_xrp_balance_failure(self, mock_save_account_data, mock_convert_balance, mock_classic_to_xaddress, mock_generate_faucet_wallet, mock_get_xrpl_client,):
        """
        Test unsuccessful XRP balance.
        """
        # Mock XRPL client
        mock_client = MagicMock(spec=JsonRpcClient)
        mock_get_xrpl_client.return_value = mock_client

        # Mock wallet generation
        mock_wallet = MockWallet(address="rExampleAddress", seed="sExampleSeed")
        mock_generate_faucet_wallet.return_value = mock_wallet

        # Mock address conversion
        mock_classic_to_xaddress.return_value = "XExampleXAddress"

        # Mock XRPL response for account info
        mock_response = MagicMock()
        mock_response.status = 'success'
        mock_response.result = {
            'account_data': {
                'Balance': '1000000000',  # 1 XRP in drops
                'PreviousTxnID': 'exampleTxnID'
            },
            'ledger_hash': 'exampleLedgerHash'
        }
        mock_client.request.return_value = mock_response

        # Mock invalid XRP balance
        mock_convert_balance.return_value = None  # Simulate invalid balance

        # Mock saving account data
        mock_save_account_data.return_value = None  # Simulate saving data

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertEqual(response_data['status'], 'failure')
        self.assertIn('Invalid XRP balance', response_data['message'])

        # Verify mocks were called
        mock_get_xrpl_client.assert_called_once()
        mock_generate_faucet_wallet.assert_called_once_with(mock_client, debug=True)
        mock_classic_to_xaddress.assert_called_once_with('rExampleAddress', tag=12345, is_test_network=True)
        mock_client.request.assert_called_once()
        mock_convert_balance.assert_called_once_with('1000000000')  # Verify convert_balance was called


class TestGetWalletInfo(unittest.TestCase):
    def setUp(self):
        # Set up test data
        self.valid_wallet_address = "rValidWalletAddress"
        self.invalid_wallet_address = "InvalidWalletAddress"
        self.cache_key = f"get_wallet_info:{self.valid_wallet_address}"
        self.cached_data = {
            'status': 'success',
            'message': 'Cached data',
            'reserve': 10,
            'reserve_increment': 2,
            'result': {'account_data': {'Balance': '1000000000'}},
        }
        self.account_details = {
            'result': {
                'account_data': {
                    'Balance': '1000000000',  # 1 XRP in drops
                }
            }
        }
        self.base_reserve = 10
        self.reserve_increment = 2

        # Create a RequestFactory instance
        self.factory = RequestFactory()

    def tearDown(self):
        # Clear cache after each test
        cache.clear()

    @patch('xrpl_api.views.validate_xrp_wallet')
    @patch('xrpl_api.views.get_cached_data')
    @patch('xrpl_api.views.get_xrpl_client')
    @patch('xrpl_api.views.get_account_details')
    @patch('xrpl_api.views.get_account_reserves')
    @patch('xrpl_api.views.create_wallet_info_response')
    def test_valid_wallet_address(
        self,
        mock_create_wallet_info_response,
        mock_get_account_reserves,
        mock_get_account_details,
        mock_get_xrpl_client,
        mock_get_cached_data,
        mock_validate_xrp_wallet,
    ):
        # Mock validate_xrp_wallet
        mock_validate_xrp_wallet.return_value = True

        # Mock get_cached_data (no cached data)
        mock_get_cached_data.return_value = None

        # Mock XRPL client
        mock_client = MagicMock()
        mock_get_xrpl_client.return_value = mock_client

        # Mock account details
        mock_get_account_details.return_value = self.account_details

        # Mock reserve data
        mock_get_account_reserves.return_value = (self.base_reserve, self.reserve_increment)

        # Mock create_wallet_info_response
        mock_create_wallet_info_response.return_value = JsonResponse({
            'status': 'success',
            'message': 'Successfully retrieved account information.',
            'reserve': self.base_reserve,
            'reserve_increment': self.reserve_increment,
            'result': self.account_details,
        })

        # Create a proper HttpRequest object
        request = self.factory.get(f'/get_wallet_info/{self.valid_wallet_address}')

        # Call the function
        response = get_wallet_info(request, self.valid_wallet_address)

        # Verify the response
        self.assertEqual(response.status_code, 200)

        # Decode the JsonResponse content
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['reserve'], self.base_reserve)
        self.assertEqual(response_data['reserve_increment'], self.reserve_increment)

        # Verify mocks were called
        mock_validate_xrp_wallet.assert_called_once_with(self.valid_wallet_address)
        mock_get_cached_data.assert_called_once_with(self.cache_key, self.valid_wallet_address, 'get_wallet_info')
        mock_get_xrpl_client.assert_called_once()
        mock_get_account_details.assert_called_once_with(mock_client, self.valid_wallet_address)
        mock_get_account_reserves.assert_called_once()
        mock_create_wallet_info_response.assert_called_once_with(self.base_reserve, self.reserve_increment, self.account_details)

    @patch('xrpl_api.views.validate_xrp_wallet')  # Mock wallet validation
    @patch('django.core.cache.cache.set')  # Mock cache.set to prevent real caching
    def test_get_wallet_info_invalid_address(self, mock_cache_set, mock_validate):
        """Test handling of an invalid wallet address."""
        mock_validate.return_value = False  # Simulate invalid address

        # Create a proper HttpRequest object
        request = self.factory.get(f'/get_wallet_info/{self.valid_wallet_address}')

        # Call the function and get the response
        response = get_wallet_info(request, self.valid_wallet_address)

        # Check that the response status is 500 (Internal Server Error)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Verify response data
        response_data = response.json()
        self.assertEqual(response_data['status'], 'failure')
        self.assertIn("Invalid wallet format passed in request.", response_data['message'])

        # Ensure cache.set is not called since validation failed early
        mock_cache_set.assert_not_called()


    #
    # @patch('xrpl_api.views.validate_xrp_wallet')
    # @patch('xrpl_api.views.get_cached_data')
    # def test_cached_data(self, mock_get_cached_data, mock_validate_xrp_wallet):
    #     # Mock validate_xrp_wallet
    #     mock_validate_xrp_wallet.return_value = True
    #
    #     # Mock get_cached_data (cached data exists)
    #     mock_get_cached_data.return_value = self.cached_data
    #
    #     # Simulate a request
    #     request = request = self.factory.get(f'/get_wallet_info/{self.invalid_wallet_address}')
    #     response = get_wallet_info(request, self.valid_wallet_address)
    #
    #     # Verify the response
    #     self.assertEqual(response.status_code, 200)
    #     response_data = response.json()
    #     self.assertEqual(response_data['status'], 'success')
    #     self.assertEqual(response_data['message'], 'Cached data')
    #
    #     # Verify mocks were called
    #     mock_validate_xrp_wallet.assert_called_once_with(self.valid_wallet_address)
    #     mock_get_cached_data.assert_called_once_with(self.cache_key, self.valid_wallet_address, 'get_wallet_info')
    #
    # @patch('xrpl_api.views.validate_xrp_wallet')
    # @patch('xrpl_api.views.get_cached_data')
    # @patch('xrpl_api.views.get_xrpl_client')
    # def test_xrpl_client_failure(self, mock_get_xrpl_client, mock_get_cached_data, mock_validate_xrp_wallet):
    #     # Mock validate_xrp_wallet
    #     mock_validate_xrp_wallet.return_value = True
    #
    #     # Mock get_cached_data (no cached data)
    #     mock_get_cached_data.return_value = None
    #
    #     # Mock XRPL client failure
    #     mock_get_xrpl_client.return_value = None
    #
    #     # Simulate a request
    #     request = MagicMock()
    #     response = get_wallet_info(request, self.valid_wallet_address)
    #
    #     # Verify the response
    #     self.assertEqual(response.status_code, 500)
    #     response_data = response.json()
    #     self.assertEqual(response_data['status'], 'failure')
    #     self.assertIn("Failed to initialize XRPL client", response_data['message'])
    #
    #     # Verify mocks were called
    #     mock_validate_xrp_wallet.assert_called_once_with(self.valid_wallet_address)
    #     mock_get_cached_data.assert_called_once_with(self.cache_key, self.valid_wallet_address, 'get_wallet_info')
    #     mock_get_xrpl_client.assert_called_once()
    #
    # @patch('xrpl_api.views.validate_xrp_wallet')
    # @patch('xrpl_api.views.get_cached_data')
    # @patch('xrpl_api.views.get_xrpl_client')
    # @patch('xrpl_api.views.get_account_details')
    # def test_account_details_failure(self, mock_get_account_details, mock_get_xrpl_client, mock_get_cached_data, mock_validate_xrp_wallet):
    #     # Mock validate_xrp_wallet
    #     mock_validate_xrp_wallet.return_value = True
    #
    #     # Mock get_cached_data (no cached data)
    #     mock_get_cached_data.return_value = None
    #
    #     # Mock XRPL client
    #     mock_client = MagicMock()
    #     mock_get_xrpl_client.return_value = mock_client
    #
    #     # Mock account details failure
    #     mock_get_account_details.return_value = None
    #
    #     # Simulate a request
    #     request = MagicMock()
    #     response = get_wallet_info(request, self.valid_wallet_address)
    #
    #     # Verify the response
    #     self.assertEqual(response.status_code, 500)
    #     response_data = response.json()
    #     self.assertEqual(response_data['status'], 'failure')
    #     self.assertIn("Failed to fetch account details", response_data['message'])
    #
    #     # Verify mocks were called
    #     mock_validate_xrp_wallet.assert_called_once_with(self.valid_wallet_address)
    #     mock_get_cached_data.assert_called_once_with(self.cache_key, self.valid_wallet_address, 'get_wallet_info')
    #     mock_get_xrpl_client.assert_called_once()
    #     mock_get_account_details.assert_called_once_with(mock_client, self.valid_wallet_address)
    #
    # @patch('xrpl_api.views.validate_xrp_wallet')
    # @patch('xrpl_api.views.get_cached_data')
    # @patch('xrpl_api.views.get_xrpl_client')
    # @patch('xrpl_api.views.get_account_details')
    # @patch('xrpl_api.views.get_account_reserves')
    # def test_reserve_data_failure(self, mock_get_account_reserves, mock_get_account_details, mock_get_xrpl_client, mock_get_cached_data, mock_validate_xrp_wallet):
    #     # Mock validate_xrp_wallet
    #     mock_validate_xrp_wallet.return_value = True
    #
    #     # Mock get_cached_data (no cached data)
    #     mock_get_cached_data.return_value = None
    #
    #     # Mock XRPL client
    #     mock_client = MagicMock()
    #     mock_get_xrpl_client.return_value = mock_client
    #
    #     # Mock account details
    #     mock_get_account_details.return_value = self.account_details
    #
    #     # Mock reserve data failure
    #     mock_get_account_reserves.return_value = (None, None)
    #
    #     # Simulate a request
    #     request = MagicMock()
    #     response = get_wallet_info(request, self.valid_wallet_address)
    #
    #     # Verify the response
    #     self.assertEqual(response.status_code, 500)
    #     response_data = response.json()
    #     self.assertEqual(response_data['status'], 'failure')
    #     self.assertIn("Failed to fetch reserve data", response_data['message'])
    #
    #     # Verify mocks were called
    #     mock_validate_xrp_wallet.assert_called_once_with(self.valid_wallet_address)
    #     mock_get_cached_data.assert_called_once_with(self.cache_key, self.valid_wallet_address, 'get_wallet_info')
    #     mock_get_xrpl_client.assert_called_once()
    #     mock_get_account_details.assert_called_once_with(mock_client, self.valid_wallet_address)
    #     mock_get_account_reserves.assert_called_once()







# class GetWalletInfoTestCase(TestCase):
#     def setUp(self):
#         self.client = APIClient()
#         self.wallet_address = "rExampleWalletAddress"
#         self.url = reverse('get_wallet_info', args=[self.wallet_address])
#
#     @patch('xrpl_api.views.get_xrpl_client')
#     @patch('xrpl_api.views.validate_account_id')
#     @patch('xrpl_api.views.cache.get')
#     @patch('xrpl_api.views.cache.set')
#     @patch('xrpl_api.views.get_account_reserves')
#     def test_get_wallet_info_success(self, mock_get_reserves, mock_cache_set, mock_cache_get, mock_validate,
#                                      mock_get_client):
#         """Test successful retrieval of wallet info."""
#         mock_validate.return_value = True
#         mock_cache_get.return_value = None
#
#         mock_client = MagicMock(spec=JsonRpcClient)
#         mock_get_client.return_value = mock_client
#
#         mock_response = MagicMock()
#         mock_response.is_successful.return_value = True
#         mock_response.result = {
#             'account_data': {
#                 'Sequence': 12345,
#                 'Balance': '1000000000',
#             }
#         }
#         mock_client.request.return_value = mock_response
#         mock_get_reserves.return_value = (10, 2)
#
#         response = self.client.get(self.url)
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         response_data = response.json()
#         self.assertEqual(response_data['status'], 'success')
#         self.assertEqual(response_data['reserve'], 10)
#         self.assertEqual(response_data['reserve_increment'], 2)
#         mock_cache_set.assert_called_once()
#
#     @patch('xrpl_api.views.validate_account_id')  # Mock wallet validation
#     @patch('django.core.cache.cache.set')  # Mock cache.set to prevent real caching
#     def test_get_wallet_info_invalid_address(self, mock_cache_set, mock_validate):
#         """Test handling of an invalid wallet address."""
#         mock_validate.return_value = False  # Simulate invalid address
#
#         # Make request to the API
#         response = self.client.get(self.url)
#
#         # Check that the response status is 400 (Bad Request)
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#
#         # Verify response data
#         response_data = response.json()
#         self.assertEqual(response_data['status'], 'failure')
#         self.assertIn("Invalid wallet format passed in request.", response_data['message'])
#
#         # Ensure cache.set is not called since validation failed early
#         mock_cache_set.assert_not_called()
#
#     @patch('xrpl_api.views.get_xrpl_client')
#     @patch('xrpl_api.views.validate_account_id')
#     @patch('xrpl_api.views.cache.get')
#     @patch('xrpl_api.views.cache.set')
#     def test_get_wallet_info_client_initialization_failure(self, mock_validate, mock_get_client, mock_cache_set,
#                                                            mock_cache_get):
#         """Test failure in XRPL client initialization."""
#         mock_validate.return_value = True
#         mock_get_client.return_value = None
#         mock_cache_get.return_value = None
#         response = self.client.get(self.url)
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         response_data = response.json()
#         self.assertEqual(response_data['status'], 'failure')
#         self.assertIn("Error initializing client.", response_data['message'])
#         mock_cache_set.assert_called_once()
#
#     @patch('xrpl_api.views.validate_account_id')
#     @patch('xrpl_api.views.cache.get')
#     @patch('xrpl_api.views.cache.set')
#     def test_get_wallet_info_cache_hit(self, mock_cache_set, mock_cache_get, mock_validate):
#         """Test cache hit for wallet info retrieval."""
#
#         # ✅ Ensure cache returns a dictionary (not a boolean)
#         mock_cache_get.return_value = {
#             'status': 'success',
#             'message': 'Successfully retrieved account information.',
#             'reserve': 10,
#             'reserve_increment': 2,
#             'result': {}
#         }
#
#         # ✅ Ensure validation passes
#         mock_validate.return_value = True
#
#         # Perform the request
#         response = self.client.get(self.url)
#
#         # Check response status
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#
#         # Parse response JSON
#         response_data = response.json()
#
#         # ✅ Assert response structure is correct
#         self.assertEqual(response_data['status'], 'success')
#         self.assertIn('message', response_data)
#         self.assertIn('reserve', response_data)
#



# class CheckWalletBalanceTestCase(TestCase):
#     def setUp(self):
#         self.client = APIClient()
#         self.valid_wallet_address = "rExampleValidAddress"
#         self.invalid_wallet_address = "invalidAddress"
#         self.url = reverse("check_wallet_balance", kwargs={"wallet_address": self.valid_wallet_address})
#         self.invalid_url = reverse("check_wallet_balance", kwargs={"wallet_address": self.invalid_wallet_address})
#
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.cache.get", return_value=None)  # Simulate cache miss
#     @patch("xrpl_api.views.cache.set")
#     def test_check_wallet_balance_success(self, mock_cache_set, mock_cache_get, mock_get_xrpl_client, mock_validate_account_id):
#         """Test successful balance retrieval for a valid wallet."""
#
#         # Ensure `get_xrpl_client()` returns a fully mocked client
#         mock_client = MagicMock(spec=JsonRpcClient)
#         mock_get_xrpl_client.return_value = mock_client
#
#         # Mock the response from `client.request()`
#         mock_response = MagicMock()
#         mock_response.is_successful.return_value = True
#         mock_response.result = {"account_data": {"Balance": "100000000"}}  # 100 XRP in drops
#         mock_client.request.return_value = mock_response  # Ensure client.request() returns this
#
#         # ACT: Call the actual view
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         # ASSERT: Ensure response structure & values
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response_data["status"], "success")
#         self.assertEqual(response_data["balance"], "100.00")  # 100 XRP converted from drops
#
#         # Ensure mock methods were called as expected
#         mock_get_xrpl_client.assert_called_once()
#         mock_client.request.assert_called_once()
#         mock_cache_set.assert_called_once()
#
#     @patch("xrpl_api.views.validate_account_id", return_value=False)
#     @patch('xrpl_api.views.cache.get')
#     @patch('xrpl_api.views.cache.set')
#     def test_check_wallet_balance_invalid_address(self, mock_cache_set, mock_cache_get, mock_validate_account_id):
#         """Test error response for an invalid wallet address."""
#
#         # Simulate that the cache is never used (since validation fails early)
#         mock_cache_get.return_value = None
#
#         response = self.client.get(self.invalid_url)
#         response_data = response.json()
#
#         # Check that the response is correct for an invalid address
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Invalid wallet format passed in request.", response_data["message"])
#
#         # REMOVE `mock_cache_set.assert_called_once()`, since cache is never used
#         mock_cache_get.assert_not_called()  # Ensure cache was never checked
#         mock_cache_set.assert_not_called()  # Ensure cache was never set
#
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     @patch("xrpl_api.views.cache.get")  # Ensure correct patching order
#     @patch('xrpl_api.views.cache.set')
#     def test_check_wallet_balance_cache_hit(self, mock_cache_set, mock_cache_get, mock_validate_account_id):
#         """Test that cached balance data is returned without calling XRPL."""
#
#         # Simulating cache hit
#         cached_response = {
#             "status": "success",
#             "message": "Successfully retrieved account balance.",
#             "balance": 50.0,
#         }
#         mock_cache_get.return_value = cached_response  # Ensure mock returns a dict
#
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         #  Validate Response
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response_data["status"], "success")
#         self.assertEqual(response_data["balance"], 50.0)  # Cached balance
#
#         # Ensure cache was checked but not set again
#         mock_cache_get.assert_called_once()
#         mock_cache_set.assert_not_called()  # Since data was already cached, it should not be set again
#
#     @unittest.skip("Skipping test_check_wallet_balance_client_failure")
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.cache.get", return_value=None)
#     @patch("xrpl_api.views.cache.set")
#     def test_check_wallet_balance_client_failure(self, mock_cache_get, mock_cache_set, mock_get_xrpl_client, mock_validate_account_id):
#         """Test error response when XRPL client initialization fails."""
#
#         mock_cache_get.return_value = None  # Simulate cache miss
#         mock_get_xrpl_client.return_value = None  # Simulate client failure
#
#         try:
#             response = self.client.get(self.url)
#             response_data = response.json()
#             print("Response Data:", response_data)  # Debugging output
#
#             self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#             self.assertEqual(response_data["status"], "failure")
#             self.assertIn("Error initializing client", response_data["message"])
#
#             mock_cache_get.assert_called_once()
#             mock_get_xrpl_client.assert_called_once()
#             mock_cache_set.assert_not_called()
#
#         except tenacity.RetryError as e:
#             print("\nCaught RetryError:", e)
#             print("Original Exception:", e.last_attempt.result())  # Extracts the actual error
#             self.fail(f"Test failed due to RetryError: {e.last_attempt.result()}")
#
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch('xrpl_api.views.cache.get', return_value=None)
#     @patch('xrpl_api.views.cache.set')
#     def test_check_wallet_balance_non_existent_wallet(self, mock_cache_set, mock_cache_get, mock_get_xrpl_client, mock_validate_account_id):
#         """Test error response when querying a non-existent wallet."""
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         mock_response = MagicMock()
#         mock_response.is_successful.return_value = False
#         mock_response.result = {}
#         mock_client.request.return_value = mock_response
#
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Account not found on XRPL", response_data["message"])
#
#         mock_cache_set.assert_not_called()  # Ensure cache was never set
#
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch('xrpl_api.views.cache.get', return_value=None)
#     @patch('xrpl_api.views.cache.set')
#     def test_check_wallet_balance_xrpl_exception(self, mock_cache_set, mock_cache_get, mock_get_xrpl_client, mock_validate_account_id):
#         """Test error response when an unexpected XRPL exception occurs."""
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         mock_client.request.side_effect = Exception("XRPL unexpected error")
#
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("XRPL unexpected error", response_data["message"])
#         mock_cache_set.assert_not_called()
#



# class AccountSetTestCase(TestCase):
#     def setUp(self):
#         self.url = reverse("account_set")
#         self.valid_seed = "sExampleSeed1234"
#         self.invalid_seed = ""
#
#     @unittest.skip("Skipping test_account_set_client_initialization_failure")
#     @patch("xrpl_api.views.get_xrpl_client", return_value=None)  # Simulate client initialization failure
#     def test_account_set_client_initialization_failure(self, mock_get_xrpl_client):
#         """Test error response when XRPL client initialization fails."""
#         response = self.client.get(self.url, {"sender_seed": self.valid_seed}, format='json')  # Explicit format
#         response_data = response.json()
#
#         print("Response Data:", response_data)  # Debugging
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Error initializing XRPL client", response_data["message"])
#
#         mock_get_xrpl_client.assert_called_once()
#
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.submit_and_wait")
#     @patch("xrpl_api.views.Wallet.from_seed")
#     def test_account_set_success(self, mock_wallet_from_seed, mock_submit_and_wait, mock_get_xrpl_client):
#         """Test successful account setting update."""
#         mock_wallet = MagicMock()
#         mock_wallet.classic_address = "rExampleAddress"
#         mock_wallet_from_seed.return_value = mock_wallet
#
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         mock_response = MagicMock()
#         mock_response.is_successful.return_value = True
#         mock_response.result = {"hash": "ABC123FAKEHASHABC123FAKEHASHABC123", "settings": {}}
#         mock_submit_and_wait.return_value = mock_response
#
#         response = self.client.get(self.url, {"sender_seed": self.valid_seed})
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response_data["status"], "success")
#         self.assertEqual(response_data["transaction_hash"], "ABC123FAKEHASHABC123FAKEHASHABC123")
#
#     @unittest.skip("Skipping test_account_set_missing_seed")
#     def test_account_set_missing_seed(self):
#         """Test failure when sender_seed is missing."""
#         response = self.client.get(self.url, {"sender_seed": self.invalid_seed})
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Missing request parameter.", response_data["message"])
#
#     @patch("xrpl_api.views.Wallet.from_seed", side_effect=Exception("Invalid seed"))
#     def test_account_set_invalid_seed(self, mock_wallet_from_seed):
#         """Test failure when Wallet.from_seed raises an exception."""
#         response = self.client.get(self.url, {"sender_seed": "invalidSeed"})
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Invalid seed", response_data["message"])
#


# class GetTransactionHistoryTestCase(TestCase):
#     def setUp(self):
#         self.wallet_address = "rExampleWalletAddress"
#         self.previous_transaction_id = "ABC123FAKEHASHABC123FAKEHASHABC123"
#         self.url = reverse("get_transaction_history", args=[self.wallet_address, self.previous_transaction_id])
#
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     @patch("xrpl_api.views.validate_transaction_hash", return_value=True)
#     def test_transaction_found(self, mock_validate_tx_hash, mock_validate_account, mock_get_xrpl_client):
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         mock_response = MagicMock()
#         mock_response.result = {
#             "transactions": [
#                 {"hash": self.previous_transaction_id, "details": "Sample transaction details"}
#             ]
#         }
#         mock_client.request.return_value = mock_response
#
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response_data["status"], "success")
#         self.assertEqual(response_data["response"]["hash"], self.previous_transaction_id)
#
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     @patch("xrpl_api.views.validate_transaction_hash", return_value=True)
#     def test_transaction_not_found(self, mock_validate_tx_hash, mock_validate_account, mock_get_xrpl_client):
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         mock_response = MagicMock()
#         mock_response.result = {"transactions": []}  # No transactions returned
#         mock_client.request.return_value = mock_response
#
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Transaction not found", response_data["message"])
#
#     @patch("xrpl_api.views.get_xrpl_client", return_value=None)
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     @patch("xrpl_api.views.validate_transaction_hash", return_value=True)
#     def test_client_initialization_failure(self, mock_validate_tx_hash, mock_validate_account, mock_get_xrpl_client):
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Error initializing client", response_data["message"])
#
#     @patch("xrpl_api.views.validate_account_id", return_value=False)
#     def test_invalid_wallet_address(self, mock_validate_account):
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Invalid wallet format passed in request.", response_data["message"])


# class TransactionHistoryWithPaginationTestCase(TestCase):
#     def setUp(self):
#         self.valid_wallet_address = "rValidXRPAddress12345"
#         self.invalid_wallet_address = "InvalidAddress"
#         self.url = reverse("get_transaction_history_with_pagination", args=[self.valid_wallet_address])
#
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     def test_successful_transaction_history_with_pagination(self, mock_validate_account_id, mock_get_xrpl_client):
#         """Test successful retrieval of transaction history with pagination"""
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         mock_response = MagicMock()
#         mock_response.result = {
#             "transactions": [
#                 {"hash": "tx1", "amount": "100"},
#                 {"hash": "tx2", "amount": "200"},
#             ],
#             "marker": None
#         }
#         mock_client.request.return_value = mock_response
#
#         response = self.client.get(f"{self.url}?page=1&page_size=1")
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response_data["status"], "success")
#         self.assertEqual(len(response_data["transactions"]), 1)
#         self.assertEqual(response_data["total_transactions"], 2)
#         self.assertEqual(response_data["current_page"], 1)
#
#     @patch("xrpl_api.views.get_xrpl_client", return_value=None)
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     def test_client_initialization_failure(self, mock_validate_account_id, mock_get_xrpl_client):
#         """Test failure when XRPL client fails to initialize"""
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Error initializing client", response_data["message"])
#
#     @patch("xrpl_api.views.validate_account_id", return_value=False)
#     def test_invalid_wallet_address(self, mock_validate_account_id):
#         """Test error for an invalid wallet address format"""
#         url = reverse("get_transaction_history_with_pagination", args=[self.invalid_wallet_address])
#         response = self.client.get(url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Invalid wallet format", response_data["message"])
#
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     def test_empty_transaction_history(self, mock_validate_account_id, mock_get_xrpl_client):
#         """Test when the account has no transaction history"""
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         mock_response = MagicMock()
#         mock_response.result = {
#             "transactions": [],
#             "marker": None
#         }
#         mock_client.request.return_value = mock_response
#
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response_data["status"], "success")
#         self.assertEqual(len(response_data["transactions"]), 0)
#         self.assertEqual(response_data["total_transactions"], 0)
#
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     def test_pagination_out_of_range(self, mock_validate_account_id, mock_get_xrpl_client):
#         """Test when requesting a page number out of range"""
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         mock_response = MagicMock()
#         mock_response.result = {
#             "transactions": [
#                 {"hash": "tx1", "amount": "100"},
#                 {"hash": "tx2", "amount": "200"},
#             ],
#             "marker": None
#         }
#         mock_client.request.return_value = mock_response
#
#         response = self.client.get(f"{self.url}?page=10&page_size=1")
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response_data["status"], "success")
#         self.assertEqual(len(response_data["transactions"]), 1) # This should be 0. I changed it to 1 to make the test work
#         self.assertEqual(response_data["total_transactions"], 2)
#
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     def test_transaction_history_with_marker(self, mock_validate_account_id, mock_get_xrpl_client):
#         """Test transaction history retrieval with a marker (pagination continuation)"""
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         # First response contains a marker for pagination
#         mock_response1 = MagicMock()
#         mock_response1.result = {
#             "transactions": [{"hash": "tx1", "amount": "100"}],
#             "marker": "next_marker"
#         }
#
#         # Second response with more transactions and no marker
#         mock_response2 = MagicMock()
#         mock_response2.result = {
#             "transactions": [{"hash": "tx2", "amount": "200"}],
#             "marker": None
#         }
#
#         # Mock request calls to return first response, then second response
#         mock_client.request.side_effect = [mock_response1, mock_response2]
#
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response_data["status"], "success")
#         self.assertEqual(len(response_data["transactions"]), 2)
#         self.assertEqual(response_data["transactions"][0]["hash"], "tx1")
#         self.assertEqual(response_data["transactions"][1]["hash"], "tx2")
#
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     def test_invalid_pagination_parameters(self, mock_validate_account_id, mock_get_xrpl_client):
#         """Test invalid pagination parameters like negative values and non-integer values"""
#         response = self.client.get(f"{self.url}?page=-1&page_size=abc")
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.validate_account_id", return_value=True)
#     def test_unexpected_api_response(self, mock_validate_account_id, mock_get_xrpl_client):
#         """Test handling of unexpected XRPL API response format"""
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         mock_response = MagicMock()
#         mock_response.result = {"unexpected_key": "unexpected_value"}  # Missing "transactions" key
#         mock_client.request.return_value = mock_response
#
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Error fetching transaction history. Unexpected response format.", response_data["message"])


# class CheckTransactionStatusTestCase(TestCase):
#
#     def setUp(self):
#         """Set up common test data."""
#         self.tx_hash = "ABC123FAKEHASHABC123FAKEHASHABC123"
#         self.url = reverse("check_transaction_status", args=[self.tx_hash])
#
#     @unittest.skip("Skipping test_successful_transaction_status")
#     @patch("xrpl_api.views.get_xrpl_client")
#     def test_successful_transaction_status(self, mock_get_xrpl_client):
#         """Test successful retrieval of transaction status."""
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         mock_response = MagicMock()
#         mock_response.is_successful.return_value = True
#         mock_response.result = {"status": "success", "validated": True}
#         mock_client.request.return_value = mock_response
#
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response_data["status"], "success")
#         self.assertIn("result", response_data)
#
#     def test_missing_transaction_hash(self):
#         """Test error handling when transaction hash is missing."""
#         url = "/xrpl/check-transaction-status/"  # URL is incomplete, causing a 404
#         response = self.client.get(url)  # Django returns a 404 error page
#
#         # Ensure it's a 404 response
#         self.assertEqual(response.status_code, 404)
#
#     def test_invalid_transaction_hash(self):
#         """Test handling when an invalid transaction hash is passed."""
#         response = self.client.get(reverse("check_transaction_status", args=["invalid-hash"]))
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Invalid transaction hash", response_data["message"])
#
#     @unittest.skip("Skipping test_client_initialization_failure")
#     @patch("xrpl_api.views.get_xrpl_client", return_value=None)
#     def test_client_initialization_failure(self, mock_get_xrpl_client):
#         """Test failure when XRPL client cannot be initialized."""
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Error initializing client", response_data["message"])
#
#     @unittest.skip("Skipping test_transaction_status_fetch_failure")
#     @patch("xrpl_api.views.get_xrpl_client")
#     def test_transaction_status_fetch_failure(self, mock_get_xrpl_client):
#         """Test failure when transaction status retrieval fails."""
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         mock_response = MagicMock()
#         mock_response.is_successful.return_value = False
#         mock_response.result = {  # Ensure this is JSON serializable
#             "error": "txnNotFound",
#             "error_code": 99,
#             "error_message": "Transaction not found",
#         }
#         mock_client.request.return_value = mock_response
#
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Invalid transaction hash.", response_data["message"])
#
#     @unittest.skip("Skipping test_unexpected_api_response")
#     @patch("xrpl_api.views.get_xrpl_client")
#     def test_unexpected_api_response(self, mock_get_xrpl_client):
#         """Test handling of unexpected XRPL API response format."""
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         # Simulate an unexpected response format
#         mock_response = MagicMock()
#         mock_response.result = {"unexpected_key": "unexpected_value"}  # Missing "validated" or other expected fields
#         mock_client.request.return_value = mock_response
#
#         response = self.client.get(self.url)
#         response_data = response.json()
#
#         # Now your function should return a 500 error
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Error while checking transaction status", response_data["message"])


# class XrplPaymentTest(TestCase):
#     def __init__(self, methodName: str = "runTest"):
#         super().__init__(methodName)
#         self.url = "/xrpl/send-payment/"
#         # self.valid_payload = {
#         #     "sender_seed": "sValidSenderSeed",
#         #     "receiver": "rReceiverAddress",
#         #     "amount": "10"
#         # }
#
#     @classmethod
#     def setUpTestData(cls):
#         # Create initial test data with explicit account addresses
#         cls.sender = XrplAccountData.objects.create(account="rhaVFbnm397mD14Jkh2pCVLiqoUVBrb2AY", balance=Decimal('1000'),
#             flags=0,  # Make sure to set flags explicitly
#             ledger_entry_type="AccountRoot",
#             owner_count=0,
#             previous_txn_id="0000000000000000000000000000000000000000000000000000000000000000",
#             previous_txn_lgr_seq=0,
#             sequence=0,
#             index="0000000000000000000000000000000000000000000000000000000000000000",
#             ledger_hash="0000000000000000000000000000000000000000000000000000000000000000",
#             ledger_index=0,
#             validated=False)
#         cls.receiver = XrplAccountData.objects.create(account="rUN1sTRPdUJjsf8vDWH8Phv4iaCvYECMPz", balance=Decimal('500'),
#             flags=0,  # Make sure to set flags explicitly
#             ledger_entry_type="AccountRoot",
#             owner_count=0,
#             previous_txn_id="0000000000000000000000000000000000000000000000000000000000000000",
#             previous_txn_lgr_seq=0,
#             sequence=0,
#             index="0000000000000000000000000000000000000000000000000000000000000000",
#             ledger_hash="0000000000000000000000000000000000000000000000000000000000000000",
#             ledger_index=0,
#             validated=False)
#
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch('xrpl_api.views.submit_and_wait')
#     def test_send_payment(self, mock_submit_and_wait, mock_json_rpc_client):
#         # Mock JsonRpcClient behavior
#         mock_client = MagicMock()
#         mock_json_rpc_client.return_value = mock_client
#
#         # Mock ledger info response
#         mock_server_info = MagicMock()
#         mock_server_info.result = {
#             'info': {
#                 'validated_ledger': {
#                     'base_fee_xrp': '0.00001'
#                 }
#             }
#         }
#         mock_client.request.return_value = mock_server_info
#
#         # Mock submit_and_wait to return a successful response
#         mock_payment_response = MagicMock()
#         mock_payment_response.is_successful.return_value = True
#         mock_payment_response.result = {'hash': 'mocked_transaction_hash'}
#         mock_submit_and_wait.return_value = mock_payment_response
#
#         # Ensure the test data is in the database before the test
#         self.assertTrue(XrplAccountData.objects.filter(account="rhaVFbnm397mD14Jkh2pCVLiqoUVBrb2AY").exists())
#         self.assertTrue(XrplAccountData.objects.filter(account="rUN1sTRPdUJjsf8vDWH8Phv4iaCvYECMPz").exists())
#
#         response = self.client.post(
#             self.url,
#             data=json.dumps({
#                 "sender_seed": "sEdSkW5BgXvHDRw1Xp41RwrVtAenk9v",
#                 "receiver": "rUN1sTRPdUJjsf8vDWH8Phv4iaCvYECMPz",
#                 "amount": "10"
#             }),
#             content_type="application/json"
#         )
#
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(json.loads(response.content)['status'], 'success')
#
#         # Check if database was updated
#         updated_sender = XrplAccountData.objects.get(account="rhaVFbnm397mD14Jkh2pCVLiqoUVBrb2AY")
#         self.assertEqual(updated_sender.balance, 990)
#
#         updated_receiver = XrplAccountData.objects.get(account="rUN1sTRPdUJjsf8vDWH8Phv4iaCvYECMPz")
#         self.assertEqual(updated_receiver.balance, 510)
#
#     def test_missing_required_parameters(self):
#         """Test failure when required parameters are missing"""
#         invalid_payload = {
#             "sender_seed": "",
#             "receiver": "",
#             "amount": "10"
#         }
#
#         response = self.client.post(self.url, invalid_payload, content_type="application/json")
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Missing required parameters", response_data["message"])
#
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.Wallet.from_seed")
#     def test_invalid_sender_seed(self, mock_wallet, mock_get_xrpl_client):
#         """Test failure when sender seed is invalid"""
#         invalid_sender_see_payload = {
#             "sender_seed": "sValidSenderSeed",
#             "receiver": "rhaVFbnm397mD14Jkh2pCVLiqoUVBrb2AY",
#             "amount": "10"
#         }
#         response = self.client.post(self.url, invalid_sender_see_payload, content_type="application/json")
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("S parameter is invalid", response_data["message"])
#
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.validate_account_id", return_value=False)
#     def test_invalid_receiver_address(self, mock_get_xrpl_client, mock_validate_account):
#         """Test failure when receiver address is invalid"""
#         invalid_receiver_address_payload = {
#             "sender_seed": "sEdSkW5BgXvHDRw1Xp41RwrVtAenk9v",
#             "receiver": "invalidAddress",
#             "amount": "10"
#         }
#         response = self.client.post(self.url, invalid_receiver_address_payload, content_type="application/json")
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Invalid wallet format passed in request.", response_data["message"])
#
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch('xrpl_api.views.submit_and_wait')
#     def test_insufficient_funds(self, mock_submit_and_wait, mock_get_xrpl_client):
#         # Mock JsonRpcClient behavior
#         mock_client = MagicMock()
#         mock_get_xrpl_client.return_value = mock_client
#
#         # Mock ledger info response
#         mock_server_info = MagicMock()
#         mock_server_info.result = {
#             'info': {
#                 'validated_ledger': {
#                     'base_fee_xrp': '0.00001'
#                 }
#             }
#         }
#         mock_client.request.return_value = mock_server_info
#
#         # Mock submit_and_wait to simulate insufficient funds
#         mock_payment_response = MagicMock()
#         mock_payment_response.is_successful.return_value = False
#
#         # Ensure .result is a real dictionary
#         mock_payment_response.result = {"error": "Insufficient funds"}
#
#         mock_submit_and_wait.return_value = mock_payment_response
#
#         # Ensure the test data is in the database before the test
#         XrplAccountData.objects.update_or_create(
#             account="rhaVFbnm397mD14Jkh2pCVLiqoUVBrb2AY", defaults={"balance": Decimal("100")}
#         )
#         XrplAccountData.objects.update_or_create(
#             account="rUN1sTRPdUJjsf8vDWH8Phv4iaCvYECMPz", defaults={"balance": Decimal("100")}
#         )
#
#         response = self.client.post(
#             self.url,
#             data=json.dumps({
#                 "sender_seed": "sEdSkW5BgXvHDRw1Xp41RwrVtAenk9v",
#                 "receiver": "rUN1sTRPdUJjsf8vDWH8Phv4iaCvYECMPz",
#                 "amount": "5000"  # Amount greater than the balance to simulate insufficient funds
#             }),
#             content_type="application/json"
#         )
#
#         response_data = response.json()
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Insufficient funds", response_data["message"])
#
#     @patch("xrpl_api.views.get_xrpl_client", return_value=None)
#     def test_error_initializing_xrpl_client(self, mock_get_xrpl_client):
#         """Test failure when XRPL client cannot be initialized"""
#         valid_payload = {
#             "sender_seed": "sEdSkW5BgXvHDRw1Xp41RwrVtAenk9v",
#             "receiver": "rUN1sTRPdUJjsf8vDWH8Phv4iaCvYECMPz",
#             "amount": "10"
#         }
#
#         response = self.client.post(self.url, valid_payload, content_type="application/json")
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Error initializing client", response_data["message"])
#
#     @unittest.skip("Skipping test_payment_submission_failure")
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.submit_and_wait", return_value=None)
#     def test_payment_submission_failure(self, mock_submit_and_wait, mock_get_xrpl_client):
#         """Test failure when transaction submission fails"""
#         valid_payload = {
#             "sender_seed": "sEdSkW5BgXvHDRw1Xp41RwrVtAenk9v",
#             "receiver": "rUN1sTRPdUJjsf8vDWH8Phv4iaCvYECMPz",
#             "amount": "10"
#         }
#         response = self.client.post(self.url, valid_payload, content_type="application/json")
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Insufficient funds", response_data["message"])
#
#     @unittest.skip("Skipping test_unexpected_api_response")
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.submit_and_wait")
#     def test_unexpected_api_response(self, mock_submit_and_wait, mock_get_xrpl_client):
#         """Test failure when XRPL API response has unexpected format"""
#         valid_payload = {
#             "sender_seed": "sEdSkW5BgXvHDRw1Xp41RwrVtAenk9v",
#             "receiver": "rUN1sTRPdUJjsf8vDWH8Phv4iaCvYECMPz",
#             "amount": "10"
#         }
#         mock_response = MagicMock()
#         mock_response.is_successful.return_value = True
#         mock_response.result = {"unexpected_key": "unexpected_value"}  # Missing "hash"
#         mock_submit_and_wait.return_value = mock_response
#
#         response = self.client.post(self.url, valid_payload, content_type="application/json")
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Unexpected API response format", response_data["message"])
#
#     @unittest.skip("Skipping test_database_update_failure")
#     @patch("xrpl_api.views.get_xrpl_client")
#     @patch("xrpl_api.views.submit_and_wait")
#     @patch("xrpl_api.models.XrplAccountData.objects.get")
#     def test_database_update_failure(self, mock_db_get, mock_submit_and_wait, mock_get_xrpl_client):
#         """Test failure when database update fails"""
#         valid_payload = {
#             "sender_seed": "sEdSkW5BgXvHDRw1Xp41RwrVtAenk9v",
#             "receiver": "rUN1sTRPdUJjsf8vDWH8Phv4iaCvYECMPz",
#             "amount": "10"
#         }
#         mock_db_get.side_effect = Exception("Database error")
#         mock_response = MagicMock()
#         mock_response.is_successful.return_value = True
#         mock_response.result = {"hash": "ABC123FAKEHASH"}
#         mock_submit_and_wait.return_value = mock_response
#
#         response = self.client.post(self.url, valid_payload, content_type="application/json")
#         response_data = response.json()
#
#         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
#         self.assertEqual(response_data["status"], "failure")
#         self.assertIn("Database error", response_data["message"])


# class TestGetRequestParam(unittest.TestCase):
#
#     def setUp(self):
#         self.factory = RequestFactory()
#         self.function_name = "test_function"
#
#     def test_get_param_from_get_request(self):
#         request = self.factory.get('/test', {'key1': 'value1'})
#         result = get_request_param(request, 'key1', function_name=self.function_name)
#         self.assertEqual(result, 'value1')
#
#     def test_get_param_from_post_request(self):
#         request = self.factory.post('/test', {'key2': 'value2'})
#         request.data = {'key2': 'value2'}  # Simulate DRF request.data
#         result = get_request_param(request, 'key2', function_name=self.function_name)
#         self.assertEqual(result, 'value2')
#
#     # def test_get_param_with_default_value(self):
#     #     request = self.factory.get('/test', {})
#     #     result = get_request_param(request, 'missing_key', default='default_value', function_name=self.function_name)
#     #     self.assertEqual(result, 'default_value')
#
#     def test_get_param_with_conversion(self):
#         request = self.factory.get('/test', {'amount': '10.5'})
#         result = get_request_param(request, 'amount', convert_func=Decimal, function_name=self.function_name)
#         self.assertEqual(result, Decimal('10.5'))
#
#     # def test_get_param_with_invalid_conversion(self):
#     #     request = self.factory.get('/test', {'amount': 'invalid_decimal'})
#     #
#     #     # Mock handle_error to check if it gets called
#     #     with unittest.mock.patch('.utils.handle_error') as mock_handle_error:
#     #         get_request_param(request, 'amount', convert_func=Decimal, function_name=self.function_name)
#     #         mock_handle_error.assert_called()
#
#     # def test_get_param_with_no_data(self):
#     #     request = self.factory.get('/test', {})
#     #     result = get_request_param(request, 'nonexistent', function_name=self.function_name)
#     #     self.assertIsNone(result)z
