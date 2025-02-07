import { Component } from '@angular/core';
import { AccountInfoComponent } from './account-info/account-info.component';
import { RouterModule } from '@angular/router';
import { TransactionDetailComponent } from './transaction-detail/transaction-detail.component';
import { HttpClientModule } from '@angular/common/http';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterModule, AccountInfoComponent, HttpClientModule ],
  template: `<app-account-info></app-account-info>`,
})
export class AppComponent {
  title = 'XRP_Project';
}
