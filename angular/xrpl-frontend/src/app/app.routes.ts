import { TransactionDetailComponent } from './transaction-detail/transaction-detail.component';
import { AccountInfoComponent } from './account-info/account-info.component';
import { LedgerDetailComponent } from './ledger-detail/ledger-detail.component';
import { CreateAccountComponent } from './create-account/create-account.component';
import { CreateTrustLineComponent } from './create-trust-line/create-trust-line.component'; // Import the new component
import { RemoveTrustLineComponent } from './remove-trust-line/remove-trust-line.component'; // Import the new component
import { SendPaymentComponent } from './send-payment/send-payment.component'; // Import the new component
import { SendPaymentAndDeleteAccountComponent } from './send-payment-and-delete-account/send-payment-and-delete-account.component'; // Import the new component
import { SendPaymentAndBlackHoleAccountComponent } from './send-payment-and-black-hole-account/send-payment-and-black-hole-account.component'; // Import the new component
import { SendCurrencyPaymentComponent } from './send-currency-payment/send-currency-payment.component'; // Import the new component
import { CancelAccountOffersComponent } from './cancel-account-offers/cancel-account-offers.component'; // Import the new component
import { GetTrustLinesComponent } from './get-trust-lines/get-trust-lines.component'; // Import the new component
import { GetAccountOffersComponent } from './get-account-offers/get-account-offers.component'; // Import the new component
import { GetServerInfoComponent } from './get-server-info/get-server-info.component'; // Import the new component
import { GetAccountConfigComponent } from './get-account-config/get-account-config.component'; // Import the new component
import { UpdateAccountConfigComponent } from './update-account-config/update-account-config.component'; // Import the new component
import { ConnectWalletComponent } from './connect-wallet/connect-wallet.component'; // Import the new component
import { Routes } from '@angular/router';
import { LayoutComponent } from './layout/layout.component';
import { HomeComponent } from './home/home.component';

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

      { path: 'get-server-info', component: GetServerInfoComponent }, // Add this route
      { path: 'get-ledger-info/:ledgerIndex', component: LedgerDetailComponent },
      { path: '**', redirectTo: 'account-info/' }, // Remove or adjust the wildcard to avoid unintended redirects to account-info
    ]
  }
]