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

@Component({
  selector: 'app-account-info',
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
  templateUrl: './account-info.component.html',
  styleUrls: ['./account-info.component.css'],
  providers: [DatePipe],
  // encapsulation: ViewEncapsulation.None
})

export class AccountInfoComponent implements OnInit {
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

  constructor(
    private readonly xrplService: XrplService, 
    private readonly snackBar: MatSnackBar, 
    private readonly datePipe: DatePipe,
    private readonly route: ActivatedRoute,
    private readonly router: Router
  ) { }

  ngOnInit(): void {
    // Use ActivatedRoute here
    this.route.params.subscribe(params => {
      console.log(params);
    });
  }

  // Method to handle Enter key press and fetch account info and transactions
  onEnter(): void {
    if (this.wallet_address.trim()) {
      // Call both methods simultaneously
      this.fetchAccountInfo(this.wallet_address);
      this.onfetchAccountTransactions(this.wallet_address);
      this.isVisible = true;  // Show the account info when Enter is pressed
    }
  }

  fetchAccountInfo(wallet_address: string) {
    this.xrplService.getAccountInfo(wallet_address).subscribe(
      (data) => {
        this.accountInfo = data;
        this.errorMessage = '';
      },
      (error) => {
        this.errorMessage = 'Error fetching account info. Please check the account ID.';
        console.error('Error fetching account info:', error);
      }
    );
  }

 fetchAccountTransactions(wallet_address: string) {
    this.xrplService.getAccountTransactionHistoryWithPagination(wallet_address).subscribe(
      (data) => {
        this.transactions = data.transactions.map((tx: any) => tx.tx_json)
      },
      (error) => {
         console.error('Error fetching account info', error)
      }
    );
  }

  onfetchAccountTransactions(wallet_address: string, page: number = 1): void {
      this.xrplService.getAccountTransactionHistoryWithPaginations(wallet_address, page).subscribe(
          data => {
              console.log('API Response:', data);
              if (data.transactions) {
                  this.transactions = data.transactions.map((tx: any) => ({
                      ...tx.tx_json,
                      date: tx.close_time_iso,
                      // delivered_amount: tx.meta.delivered_amount,
                      delivered_amount: tx.meta.delivered_amount ?? '',
                      transaction_result: tx.meta.TransactionResult.indexOf('SUCCESS') > 0 ? 'Success' : tx.meta.TransactionResult,
                      // transaction_result: tx.meta.TransactionResult
                  }));
                  this.totalItems = data.total_transactions;
                  this.pageIndex = page - 1;
              } 
              else {
                  console.error('No transactions found in the API response');
              }
          },
          error => console.error('Error fetching account info', error)
      );
  }

  onPageChange(event: any): void {
    this.onfetchAccountTransactions(this.wallet_address, event.pageIndex + 1);
  }

  createAccount() {
    this.xrplService.createAccount().subscribe(
      (data) => {
        this.newAccount = data;
        this.snackBar.open('Account created successfully!', 'Close', {duration: 5000,});
      },
      (error) => {
        this.snackBar.open('Error creating account. Please try again.', 'Close', {duration: 5000,});
        console.error('Error creating account:', error);
      }
    );
  }

   // Navigate to the transaction page when a row is clicked
   navigateToTransaction(wallet_address: string): void {
    console.log('Navigating to:', wallet_address); 
    this.isTransactionDetails = true;
    this.router.navigate(['/transaction', wallet_address]);
    // this.xrplService.getSingleTransactionHistory(wallet_address).subscribe(
    //   (data) => {
    //     this.accountInfo = data;
    //     this.errorMessage = '';
    //   },
    //   (error) => {
    //     this.errorMessage = 'Error fetching account info. Please check the account ID.';
    //     console.error('Error fetching account info:', error);
    //   }
    // );
  }
  
  // Helper method to safely access transaction properties
  getTransactionProperty(tx: any, property: string): string {
    return tx?.tx?.[property] || 'N/A';
  }

  // Helper method to get object keys
  objectKeys(obj: any): string[] {
    return Object.keys(obj);
  }

  // Convert drops to XRP
  convertDropsToXrp(drops: string | number): number {
    return Number(drops) / 1000000;
  }
}
