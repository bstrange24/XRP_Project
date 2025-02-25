import { TransactionDetailComponent } from './transaction-detail/transaction-detail.component';
import { AccountInfoComponent } from './account-info/account-info.component';
import { LedgerDetailComponent } from './ledger-detail/ledger-detail.component';
import { CreateAccountComponent } from './create-account/create-account.component';
import { CreateTrustLineComponent } from './create-trust-line/create-trust-line.component'; // Import the new component
import { RemoveTrustLineComponent } from './remove-trust-line/remove-trust-line.component'; // Import the new component
import { SendPaymentComponent } from './send-payment/send-payment.component'; // Import the new component
import { Routes } from '@angular/router';
import { LayoutComponent } from './layout/layout.component';
import { HomeComponent } from './home/home.component';

export const routes: Routes = [
  {
    path: '',
    component: LayoutComponent, // Wrapper component for child routes
    children: [
      { path: '', component: HomeComponent, pathMatch: 'full' },
      { path: 'transaction', component: TransactionDetailComponent },
      { path: 'create-account', component: CreateAccountComponent },
      { path: 'create-trust-line', component: CreateTrustLineComponent },
      { path: 'remove-trust-line', component: RemoveTrustLineComponent },
      { path: 'send-payment', component: SendPaymentComponent }, // Add this route
      { path: 'account-info/:walletAddress', component: AccountInfoComponent },
      { path: 'get-ledger-info/:ledgerIndex', component: LedgerDetailComponent },
      { path: '**', redirectTo: 'account-info/' }, // Remove or adjust the wildcard to avoid unintended redirects to account-info
    ]
  }
]