import { Component, ViewEncapsulation, OnInit  } from '@angular/core';
import { XrplService } from '../services/xrpl-data/xrpl.service';
import { CommonModule, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatTableModule } from '@angular/material/table';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatMenuModule } from '@angular/material/menu';
import { MatSelectModule } from '@angular/material/select';
import { MatOptionModule } from '@angular/material/core';
import { MatIconModule } from '@angular/material/icon';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { SharedDataService } from '../services/shared-data/shared-data.service';

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatExpansionModule,
    MatTableModule,
    MatPaginatorModule,
    MatToolbarModule,
    MatMenuModule,
    MatSelectModule,
    MatOptionModule,
    MatIconModule,
    RouterModule,
  ],
  templateUrl: './layout.component.html',
  styleUrls: ['./layout.component.css']
})
export class LayoutComponent {
  wallet_address: string = '';
  accountInfo: any;
  transactions: any[] = [];
  errorMessage: string = '';
  // displayedColumns: string[] = ['account', 'TransactionType', 'Destination', 'ledger_index', 'delivered_amount','close_time_iso'];
  displayedColumns: string[] = ['account', 'TransactionType', 'Destination', 'TransactionResult', 'delivered_amount','close_time_iso'];
  newAccount: any = null;
  totalItems: number = 0;
  pageSize: number = 10;
  pageIndex: number = 0;
  option1: string = 'Hey';
  option2: string = 'Joe';
  id: number = 0;
  // The variable that controls visibility
  isVisible = false;
  isTransactionDetails: boolean = false;
  selectedTransaction: string = ''; // This will hold the account ID or relevant identifier for the selected transaction

  constructor(private readonly router: Router, private readonly sharedDataService: SharedDataService) {}

    // Method to handle Enter key press and fetch account info and transactions
    onEnter(): void {
      if (this.wallet_address.trim()) {
        this.sharedDataService.setWalletAddress(this.wallet_address); // Share the wallet address
        // Call both methods simultaneously
        // this.fetchAccountInfo(this.wallet_address);
        // this.onfetchAccountTransactions(this.wallet_address);
        this.isVisible = true;  // Show the account info when Enter is pressed
        // Navigate to the transaction detail page with the wallet address
        this.router.navigate(['/transaction', this.wallet_address]);
        // this.router.navigate(['/account-info', this.wallet_address]);
      }
    }
}