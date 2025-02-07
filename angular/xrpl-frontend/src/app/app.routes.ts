import { NgModule } from '@angular/core';
import { TransactionDetailComponent } from './transaction-detail/transaction-detail.component';
import { RouterModule, Routes } from '@angular/router';

export const routes: Routes = [
    { path: 'transaction/:id', component: TransactionDetailComponent },
];

@NgModule({
    imports: [RouterModule.forRoot(routes)],
    exports: [RouterModule]
  })

  export class AppRoutingModule {}