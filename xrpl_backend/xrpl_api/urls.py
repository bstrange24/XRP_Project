from django.urls import path
from .views import XRPLAccountView, XRPLAccountTransactionsView, XRPLCreateAccountView
from .views import create_account, get_account_info, check_balance, account_set
from .views import get_transaction_history, get_transaction_history_with_pagination, check_transaction_status
from .views import send_payment

urlpatterns = [
    # path('account/<str:account_id>/', XRPLAccountView.as_view(), name='xrpl-account'),
    # path('account/<str:account_id>/transactions/', XRPLAccountTransactionsView.as_view(), name='xrpl-account-transactions'),
    # path('account/create/', XRPLCreateAccountView.as_view(), name='xrpl-create-account'),

    # http://127.0.0.1:8000/xrpl/create-account/
    path('create-account/', create_account, name='create_account'),
    #  http://127.0.0.1:8000/xrpl/account-info/rMgaRbbZUBeoxwZevhv1mezuvA97eR4JHV/
    path('account-info/<str:account_id>/', get_account_info, name='get_account_info'),
    #  http://127.0.0.1:8000/xrpl/check-balance/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("check-balance/<str:address>/", check_balance, name="check_balance"),
    # http://127.0.0.1:8000/xrpl/account-set/?sender_seed=sEd742NyPHW2JUNbBeF7L9HNez6ne6B&require_destination_tag=false&disable_master_key=false&enable_regular_key=true
    path("account-set/", account_set, name="account_set"),

    # http://127.0.0.1:8000/xrpl/transaction-history/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("transaction-history/<str:address>/", get_transaction_history, name="get_transaction_history"),
    # http://127.0.0.1:8000/xrpl/transaction-history-with-pag/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("transaction-history-with-pag/<str:address>/", get_transaction_history_with_pagination,
         name="get_transaction_history_with_pagination"),
    # http://127.0.0.1:8000/xrpl/check-transaction-status/80AD9114C666200C59F0405C445BF15F30E87E01CA2154ACFF746ABAB9C67803/
    path("check-transaction-status/<str:tx_hash>/", check_transaction_status, name="check_transaction_status"),

    # http://127.0.0.1:8000/xrpl/send-payment/?sender_seed=sEd75gQcwgacU52hPDULRCmpchbKz6M&receiver=rNkE8uqaptRMAiREQv2EasKXGrgJM2TvYW&amount=10
    path('send-payment/', send_payment, name='send_payment'),
]