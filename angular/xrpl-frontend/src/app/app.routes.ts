import { TransactionDetailComponent } from './transaction-detail/transaction-detail.component';
import { AccountInfoComponent } from './account-info/account-info.component';
import { Routes } from '@angular/router';
import { LayoutComponent } from './layout/layout.component'; // Import the LayoutComponent
import { HomeComponent } from './home/home.component'; // Import the HomeComponent

// export const routes: Routes = [
//     { path: 'transaction/:wallet_address', component: TransactionDetailComponent },
//     { path: 'account-info', component: AccountInfoComponent },
//     { path: '', redirectTo: '/account-info', pathMatch: 'full' },
//     { path: '**', redirectTo: '/account-info' },
// ];

export const routes: Routes = [
    {
      path: '',
      component: LayoutComponent, // Use LayoutComponent as the wrapper
      children: [
        { path: '', component: HomeComponent }, // Home page as the default route
        { path: 'transaction/:wallet_address', component: TransactionDetailComponent },
        { path: 'account-info', component: AccountInfoComponent },
        // { path: '', redirectTo: '/account-info', pathMatch: 'full' },
        { path: '**', redirectTo: '/account-info' }, // Fallback route
      ]
    }
  ];