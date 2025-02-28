from django.contrib import admin
from django.urls import path, include

from xrpl_api.nft.nft import NftProcessing

urlpatterns = [
    path('admin/', admin.site.urls),
    path('xrpl/', include('xrpl_api.urls')),  # Include the xrpl_api app's URLs
    path('xrpl/mint-nft/', NftProcessing.as_view(), name='mint_nft'),
    path('xrpl/get-account-nft/', NftProcessing.as_view(), name='get_account_nft'),
    path('xrpl/burn-account-nft/', NftProcessing.as_view(), name='burn_account_nft'),
    path('xrpl/sell-account-nft/', NftProcessing.as_view(), name='sell_account_nft'),
    path('xrpl/buy-account-nft/', NftProcessing.as_view(), name='buy_account_nft'),
]