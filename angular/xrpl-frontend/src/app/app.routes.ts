import { TransactionDetailComponent } from './transaction-detail/transaction-detail.component';
import { AccountInfoComponent } from './account-info/account-info.component';
import { Routes } from '@angular/router';
import { LayoutComponent } from './layout/layout.component';
import { HomeComponent } from './home/home.component';

export const routes: Routes = [
    {
      path: '',
      // Use LayoutComponent as the wrapper
      component: LayoutComponent, 
      children: [
         // Home page as the default route
        { path: '', component: HomeComponent, pathMatch: 'full' },
        { path: 'transaction', component: TransactionDetailComponent },
        { path: 'account-info', component: AccountInfoComponent },
        { path: '**', redirectTo: '/account-info' },
      ]
    }
  ];