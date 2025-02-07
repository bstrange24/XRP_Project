import { Component } from '@angular/core';
import { AccountInfoComponent } from './account-info/account-info.component';
import { RouterModule, Routes  } from '@angular/router';
import { TransactionDetailComponent } from './transaction-detail/transaction-detail.component';
import { HttpClientModule } from '@angular/common/http';

// const routes: Routes = [
  // { path: 'transaction/:wallet_address', component: TransactionDetailComponent },
// ];

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    AccountInfoComponent, 
    HttpClientModule,
  ],
  template: `<app-account-info></app-account-info>`,
})
export class AppComponent {
  title = 'XRP_Project';
}
