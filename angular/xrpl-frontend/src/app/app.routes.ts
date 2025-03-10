import { ConnectWalletComponent } from './connect-wallet/connect-wallet.component';
import { Routes } from '@angular/router';
import { LayoutComponent } from './layout/layout.component';
import { HomeComponent } from './home/home.component';
import { GetNftsComponent } from './nfts/get-nfts/get-nfts/get-nfts.component';
import { RemoveTrustLineComponent } from './trustLines/remove-trust-line/remove-trust-line.component';
import { CreateTrustLineComponent } from './trustLines/create-trust-line/create-trust-line.component';
import { GetTrustLinesComponent } from './trustLines/get-trust-lines/get-trust-lines.component';
import { SendPaymentComponent } from './payments/send-payment/send-payment.component';
import { SendPaymentAndDeleteAccountComponent } from './payments/send-payment-and-delete-account/send-payment-and-delete-account.component';
import { SendPaymentAndBlackHoleAccountComponent } from './payments/send-payment-and-black-hole-account/send-payment-and-black-hole-account.component';
import { SendCurrencyPaymentComponent } from './payments/send-currency-payment/send-currency-payment.component';
import { AccountInfoComponent } from './accounts/account-info/account-info.component';
import { CreateAccountComponent } from './accounts/create-account/create-account.component';
import { GetAccountConfigComponent } from './accounts/get-account-config/get-account-config.component';
import { UpdateAccountConfigComponent } from './accounts/update-account-config/update-account-config.component';
import { TransactionDetailComponent } from './transactions/transaction-detail/transaction-detail.component';
import { GetServerInfoComponent } from './ledger/get-server-info/get-server-info.component';
import { LedgerDetailComponent } from './ledger/ledger-detail/ledger-detail.component';
import { OracleInfoComponent } from './oracles/oracle-info/oracle-info.component';
import { CreateOracleComponent } from './oracles/create-oracle/create-oracle.component';
import { DeleteOracleComponent } from './oracles/delete-oracle/delete-oracle.component';
import { DidInfoComponent } from './did/did-info/did-info.component';
import { SetDidComponent } from './did/set-did/set-did.component';
import { DeleteDidComponent } from './did/delete-did/delete-did.component';
import { EscrowInfoComponent } from './escrow/escrow-info/escrow-info.component';
import { CreateEscrowComponent } from './escrow/create-escrow/create-escrow.component';
import { CancelEscrowComponent } from './escrow/cancel-escrow/cancel-escrow.component';
import { FinishEscrowComponent } from './escrow/finish-escrow/finish-escrow.component';
import { MintNftsComponent } from './nfts/mint-nfts/mint-nfts/mint-nfts.component';
import { CancelNftsComponent } from './nfts/cancel-nfts/cancel-nfts/cancel-nfts.component';
import { BurnNftsComponent } from './nfts/burn-nfts/burn-nfts/burn-nfts.component';
import { SellNftsComponent } from './nfts/sell-nfts/sell-nfts/sell-nfts.component';
import { BuyNftsComponent } from './nfts/buy-nfts/buy-nfts/buy-nfts.component';
import { ChecksInfoComponent } from './checks/checks-info/checks-info.component';
import { CancelCheckComponent } from './checks/cancel-check/cancel-check.component';
import { CashXrpCheckComponent } from './checks/cash-xrp-check/cash-xrp-check.component';
import { CashTokenCheckComponent } from './checks/cash-token-check/cash-token-check.component';
import { CreateXrpCheckComponent } from './checks/create-xrp-check/create-xrp-check.component';
import { CreateTokenCheckComponent } from './checks/create-token-check/create-token-check.component';
import { GetAccountOffersComponent } from './offers/get-account-offers/get-account-offers.component';
import { CancelAccountOffersComponent } from './offers/cancel-account-offers/cancel-account-offers.component';

export const routes: Routes = [
     {
          path: '',
          component: LayoutComponent, // Wrapper component for child routes
          children: [
               { path: '', component: HomeComponent, pathMatch: 'full' },

               ////////////////////////// Accounts //////////////////////////
               { path: 'connect-wallet', component: ConnectWalletComponent },
               { path: 'account-info/:walletAddress', component: AccountInfoComponent },
               { path: 'create-account', component: CreateAccountComponent },
               { path: 'get-account-config', component: GetAccountConfigComponent },
               { path: 'update-account-config', component: UpdateAccountConfigComponent },

               ////////////////////////// Offers //////////////////////////
               { path: 'get-account-offers', component: GetAccountOffersComponent },
               { path: 'cancel-account-offers', component: CancelAccountOffersComponent },
               { path: 'get-book-offers', component: CancelAccountOffersComponent },
               { path: 'create-account-offers', component: CancelAccountOffersComponent },

               ////////////////////////// Transactions //////////////////////////
               { path: 'transaction', component: TransactionDetailComponent },

               ////////////////////////// Trust Lines //////////////////////////
               { path: 'create-trust-line', component: CreateTrustLineComponent },
               { path: 'remove-trust-line', component: RemoveTrustLineComponent },
               { path: 'get-trust-lines', component: GetTrustLinesComponent },

               ////////////////////////// Payments //////////////////////////
               { path: 'send-payment', component: SendPaymentComponent },
               { path: 'send-payment-and-delete-account', component: SendPaymentAndDeleteAccountComponent },
               { path: 'send-payment-and-black-hole-account', component: SendPaymentAndBlackHoleAccountComponent },
               { path: 'send-currency-payment', component: SendCurrencyPaymentComponent },

               ////////////////////////// NFTS //////////////////////////
               { path: 'get-nfts', component: GetNftsComponent },
               { path: 'mint-nfts', component: MintNftsComponent },
               { path: 'cancel-nfts', component: CancelNftsComponent },
               { path: 'buy-nfts', component: BuyNftsComponent },
               { path: 'sell-nfts', component: SellNftsComponent },
               { path: 'burn-nfts', component: BurnNftsComponent },

               ////////////////////////// Oracles //////////////////////////
               { path: 'get-price-oracle', component: OracleInfoComponent },
               { path: 'create-price-oracle', component: CreateOracleComponent },
               { path: 'delete-price-oracle', component: DeleteOracleComponent },

               ////////////////////////// DID //////////////////////////
               { path: 'get-account-did', component: DidInfoComponent },
               { path: 'set-did', component: SetDidComponent },
               { path: 'delete-did', component: DeleteDidComponent },

               ////////////////////////// Escrow //////////////////////////
               { path: 'get-account-escrow', component: EscrowInfoComponent },
               { path: 'create-escrow', component: CreateEscrowComponent },
               { path: 'cancel-escrow', component: CancelEscrowComponent },
               { path: 'finish-escrow', component: FinishEscrowComponent },

               ////////////////////////// Checks //////////////////////////
               { path: 'get-checks', component: ChecksInfoComponent },
               { path: 'create_token-check', component: CreateTokenCheckComponent },
               { path: 'create_xrp-check', component: CreateXrpCheckComponent },
               { path: 'cash-token-check', component: CashTokenCheckComponent },
               { path: 'cash-xrp-check', component: CashXrpCheckComponent },
               { path: 'cancel-check', component: CancelCheckComponent },

               ////////////////////////// Ledger //////////////////////////
               { path: 'get-server-info', component: GetServerInfoComponent },
               { path: 'get-ledger-info/:ledgerIndex', component: LedgerDetailComponent },
               { path: '**', redirectTo: '', pathMatch: 'full' }

               // { path: '**', redirectTo: 'account-info/' }, // Remove or adjust the wildcard to avoid unintended redirects to account-info
          ]
     }
]