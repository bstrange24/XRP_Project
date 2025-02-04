import { Component, ViewEncapsulation } from '@angular/core';
import { XrplService } from '../xrpl.service';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatTableModule } from '@angular/material/table'; // For displaying transactions in a table
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatMenuModule } from '@angular/material/menu';

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
    MatExpansionModule, // For expandable sections
    MatTableModule, // Add this for the transactions table
    MatPaginatorModule,
    MatToolbarModule,
    MatMenuModule,
  ],
  templateUrl: './account-info.component.html',
  styleUrls: ['./account-info.component.css'],
  encapsulation: ViewEncapsulation.None
})

export class AccountInfoComponent {
  accountId: string = '';
  accountInfo: any;
  transactions: any[] = [];
  errorMessage: string = '';
  displayedColumns: string[] = ['account', 'TransactionType', 'Destination', 'ledger_index', 'delivered_amount'];
  newAccount: any = null;
  totalItems: number = 0;
  pageSize: number = 10;
  pageIndex: number = 0;

  constructor(private xrplService: XrplService, private snackBar: MatSnackBar) { }

  fetchAccountInfo() {
    this.xrplService.getAccountInfo(this.accountId).subscribe(
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

 fetchAccountTransactions() {
    this.xrplService.getAccountTransactionHistoryWithPagination(this.accountId).subscribe(
      data => this.transactions = data.transactions.map((tx: any) => tx.tx_json),
      error => console.error('Error fetching account info', error)
    );
  }

onfetchAccountTransactions(page: number = 1): void {
    this.xrplService.getAccountTransactionHistoryWithPaginations(this.accountId, page).subscribe(
        data => {
            console.log('API Response:', data);  // Log the response to understand its structure
            if (data.transactions) {
                this.transactions = data.transactions.map((tx: any) => ({
                    ...tx.tx_json,
                    date: tx.close_time_iso,
                    delivered_amount: tx.meta.delivered_amount,
                    transaction_result: tx.meta.TransactionResult
                }));
                this.totalItems = data.total_transactions;  // Update totalItems from total_transactions
                this.pageIndex = page - 1;
            } else {
                console.error('No transactions found in the API response');
            }
        },
        error => console.error('Error fetching account info', error)
    );
}

  onPageChange(event: any): void {
    this.onfetchAccountTransactions(event.pageIndex + 1);
  }

  createAccount() {
    this.xrplService.createAccount().subscribe(
      (data) => {
        this.newAccount = data;
        this.snackBar.open('Account created successfully!', 'Close', {
          duration: 5000,
        });
      },
      (error) => {
        this.snackBar.open('Error creating account. Please try again.', 'Close', {
          duration: 5000,
        });
        console.error('Error creating account:', error);
      }
    );
  }

  // Helper method to safely access transaction properties
  getTransactionProperty(tx: any, property: string): string {
    return tx?.tx?.[property] || 'N/A';
  }

  // Helper method to get object keys
  objectKeys(obj: any): string[] {
    return Object.keys(obj);
  }
}
