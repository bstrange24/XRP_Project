import { NgModule } from '@angular/core';
import { TransactionDetailComponent } from './transaction-detail/transaction-detail.component';
import { AccountInfoComponent } from './account-info/account-info.component';
import { RouterModule, Routes } from '@angular/router';
import { CommonModule } from '@angular/common';

export const routes: Routes = [
    { path: 'transaction/:wallet_address', component: TransactionDetailComponent },
    { path: 'account-info', component: AccountInfoComponent },
    { path: '', redirectTo: '/account-info', pathMatch: 'full' },
    { path: '**', redirectTo: '/default-page' },
];

@NgModule({
    imports: [CommonModule, RouterModule.forRoot(routes)],
    exports: [RouterModule]
  })

  export class AppRoutingModule {}