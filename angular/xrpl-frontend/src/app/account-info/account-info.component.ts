import { Component, OnInit, HostListener } from '@angular/core';
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
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatMenuModule } from '@angular/material/menu';
import { MatSelectModule } from '@angular/material/select';
import { MatOptionModule } from '@angular/material/core';
import { MatIconModule } from '@angular/material/icon';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { SharedDataService } from '../services/shared-data/shared-data.service';

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
})
export class AccountInfoComponent implements OnInit {
  wallet_address: string = '';
  transactionHash: string = '';
  accountInfo: any;
  transactions: any[] = [];
  errorMessage: string = '';
  displayedColumns: string[] = ['combined'];
  newAccount: any = null;
  totalItems: number = 0;
  pageSize: number = 10;
  currentPage: number = 1;
  isLoading: boolean = false;
  hasMore: boolean = true;
  isVisible = false;
  isTransactionDetails: boolean = false;
  selectedTransaction: string = '';

  constructor(
    private readonly xrplService: XrplService,
    private readonly snackBar: MatSnackBar,
    private readonly datePipe: DatePipe,
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly sharedDataService: SharedDataService
  ) {}

  ngOnInit(): void {
    console.log('Inside AccountInfoComponent ngOnInit');
    this.sharedDataService.walletAddress$.subscribe(address => {
      if (address) {
        this.wallet_address = address;
        console.log('Wallet Address from Shared Service:', address);
        console.log('Received wallet_address:', this.wallet_address);
        this.fetchAccountInfo(this.wallet_address);
        this.loadMoreTransactions();
        this.isVisible = true;
      } else {
        console.warn('Wallet Address not found');
      }
    });

    this.sharedDataService.transactionHash$.subscribe(transactionHash => {
      this.transactionHash = transactionHash;
      console.log('Transaction Hash from Shared Service:', transactionHash);
    });

    this.route.params.subscribe(params => {
      console.log('Route Params:', params);
    });
  }

  @HostListener('wheel', ['$event'])
  onWheel(event: WheelEvent): void {
    const element = document.querySelector('.table-container');
    if (element) {
      const atBottom = element.scrollTop + element.clientHeight >= element.scrollHeight - 50;
      if (event.deltaY > 0 && atBottom && !this.isLoading && this.hasMore) {
        this.loadMoreTransactions();
      }
    }
  }

  onEnter(): void {
    if (this.wallet_address.trim()) {
      this.fetchAccountInfo(this.wallet_address);
      this.transactions = [];
      this.currentPage = 1;
      this.hasMore = true;
      this.loadMoreTransactions();
      this.isVisible = true;
    }
  }

  fetchAccountInfo(wallet_address: string) {
    console.log('Fetching account info for:', wallet_address);
    this.xrplService.getAccountInfo(wallet_address).subscribe(
      (data) => {
        this.accountInfo = data;
        this.errorMessage = '';
        console.log('Account Info:', data);
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
        this.transactions = data.transactions.map((tx: any) => tx.tx_json);
      },
      (error) => {
        console.error('Error fetching account transactions:', error);
      }
    );
  }

  loadMoreTransactions(): void {
    if (!this.hasMore || this.isLoading) {
      console.log('Skipping fetch - hasMore:', this.hasMore, 'isLoading:', this.isLoading);
      return;
    }
  
    this.isLoading = true;
    console.log('Fetching with page:', this.currentPage, 'pageSize:', this.pageSize);
    this.xrplService.getAccountTransactionHistoryWithPaginations(this.wallet_address, this.currentPage, this.pageSize).subscribe(
      data => {
        console.log('API Response:', data);
        if (data && data.transactions) {
          const newTransactions = data.transactions.map((tx: any) => {
            let additionalInfo: string;
            let tx_type: string;
            let currency: string = 'N/A';
            let issuer: string = 'N/A';
            let value: string = 'N/A';
  
            try {
              switch (tx.tx_json.TransactionType) {
                case 'TrustSet':
                  tx_type = 'SET TRUST LIMIT';
                  currency = tx.tx_json.LimitAmount?.currency || 'N/A';
                  issuer = tx.tx_json.LimitAmount?.issuer || 'N/A';
                  value = tx.tx_json.LimitAmount?.value || '0';
                  additionalInfo = `${tx_type} ${currency}$${value} ${currency}.${issuer}`;
                  break;
                case 'Payment':
                  tx_type = 'SEND';
                  // Payment uses Amount, not LimitAmount
                  if (typeof tx.meta.delivered_amount === 'string') {
                    // XRP payment (drops)
                    value = (parseInt(tx.meta.delivered_amount) / 1000000).toFixed(2);
                    currency = 'XRP';
                    issuer = tx.tx_json.Destination || 'N/A';
                  } else {
                    // Non-XRP payment (e.g., token)
                    currency = tx.meta.Amount?.currency || 'N/A';
                    issuer = tx.tx_json.Destination || 'N/A';
                    value = (parseInt(tx.meta.delivered_amount) / 1000000).toFixed(2) || '0';
                  }
                  additionalInfo = `${tx_type} ${value} ${currency} to ${issuer}`;
                  break;
                case 'AccountDelete':
                  tx_type = 'Account Delete';
                  currency = tx.tx_json.LimitAmount?.currency || 'N/A';
                  issuer = tx.tx_json.LimitAmount?.issuer || 'N/A';
                  value = tx.tx_json.LimitAmount?.value || '0';
                  additionalInfo = `${tx_type} ${currency}$${value} ${currency}.${issuer}`;
                  break;
                default:
                  additionalInfo = tx.tx_json.TransactionType; // Fallback
              }
            } catch (error) {
              console.error('Error processing transaction:', tx.tx_json.TransactionType, error);
              additionalInfo = `${tx.tx_json.TransactionType} (Error processing details)`;
            }
  
            return {
              ...tx.tx_json,
              date: tx.close_time_iso,
              delivered_amount: tx.meta.delivered_amount ?? '',
              transaction_result: tx.meta.TransactionResult.indexOf('SUCCESS') > -1 ? 'Success' : tx.meta.TransactionResult,
              additional_information: additionalInfo,
              transaction_hash: tx.hash,
            };
          });
          this.transactions = [...this.transactions, ...newTransactions];
          this.totalItems = data.total_offers || 0;
          this.currentPage++;
          this.hasMore = this.transactions.length < this.totalItems;
          console.log('Fetch complete - Total items:', this.totalItems, 'Loaded:', this.transactions.length, 'Has more:', this.hasMore, 'Next page:', this.currentPage);
        } else {
          console.warn('No transactions in API response');
          this.hasMore = false;
        }
        this.isLoading = false;
      },
      error => {
        console.error('Error fetching account transactions:', error);
        this.isLoading = false;
        this.hasMore = false;
      }
    );
  }

  navigateToTransaction(wallet_address: string, transaction_hash: string): void {
    console.log('Navigating to:', wallet_address);
    console.log('hash:', transaction_hash);
    this.sharedDataService.setTransactionHashSubject(transaction_hash);
    this.isTransactionDetails = true;
    this.router.navigate(['/transaction']);
  }

  getTransactionProperty(tx: any, property: string): string {
    return tx?.tx?.[property] || 'N/A';
  }

  objectKeys(obj: any): string[] {
    return Object.keys(obj);
  }

  convertDropsToXrp(drops: string | number): number {
    return Number(drops) / 1000000;
  }
}