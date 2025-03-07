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
import { GetAccountOffersComponent } from './accounts/get-account-offers/get-account-offers.component';
import { CancelAccountOffersComponent } from './accounts/cancel-account-offers/cancel-account-offers.component';
import { GetServerInfoComponent } from './ledger/get-server-info/get-server-info.component';
import { LedgerDetailComponent } from './ledger/ledger-detail/ledger-detail.component';
import { OracleInfoComponent } from './oracles/oracle-info/oracle-info.component';

export const routes: Routes = [
  {
    path: '',
    component: LayoutComponent, // Wrapper component for child routes
    children: [
      { path: '', component: HomeComponent, pathMatch: 'full' },

      { path: 'connect-wallet', component: ConnectWalletComponent }, // Add this route
      { path: 'account-info/:walletAddress', component: AccountInfoComponent },
      { path: 'create-account', component: CreateAccountComponent },
      { path: 'get-account-config', component: GetAccountConfigComponent }, // Add this route
      { path: 'update-account-config', component: UpdateAccountConfigComponent }, // Add this route

      { path: 'transaction', component: TransactionDetailComponent },

      { path: 'create-trust-line', component: CreateTrustLineComponent },
      { path: 'remove-trust-line', component: RemoveTrustLineComponent },
      { path: 'get-trust-lines', component: GetTrustLinesComponent }, // Add this route

      { path: 'send-payment', component: SendPaymentComponent }, // Add this rout
      { path: 'send-payment-and-delete-account', component: SendPaymentAndDeleteAccountComponent }, // Add this route
      { path: 'send-payment-and-black-hole-account', component: SendPaymentAndBlackHoleAccountComponent }, // Add this route
      { path: 'send-currency-payment', component: SendCurrencyPaymentComponent }, // Add this route
      
      { path: 'get-account-offers', component: GetAccountOffersComponent }, // Add this route
      { path: 'cancel-account-offers', component: CancelAccountOffersComponent }, // Add this route

      
      { path: 'get-nfts', component: GetNftsComponent }, // Add this route

      { path: 'get-price-oracle', component: OracleInfoComponent },


      { path: 'get-server-info', component: GetServerInfoComponent }, // Add this route
      { path: 'get-ledger-info/:ledgerIndex', component: LedgerDetailComponent },
      { path: '**', redirectTo: '', pathMatch: 'full' }

      // { path: '**', redirectTo: 'account-info/' }, // Remove or adjust the wildcard to avoid unintended redirects to account-info
    ]
  }
]