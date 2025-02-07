import { NgModule } from '@angular/core';
import { TransactionDetailComponent } from './transaction-detail/transaction-detail.component';
import { AccountInfoComponent } from './account-info/account-info.component';
import { RouterModule, Routes } from '@angular/router';

export const routes: Routes = [
    { path: 'transaction/:id', component: TransactionDetailComponent },
    { path: 'account-info', component: AccountInfoComponent },
    { path: '', redirectTo: '/account-info', pathMatch: 'full' }
];

@NgModule({
    imports: [RouterModule.forRoot(routes)],
    exports: [RouterModule]
  })

  export class AppRoutingModule {}