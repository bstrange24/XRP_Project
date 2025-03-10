import { Component, OnInit, ChangeDetectorRef, HostListener } from '@angular/core';
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
import { MatTabsModule, MatTabChangeEvent } from '@angular/material/tabs';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { XrplService } from '../../services/xrpl-data/xrpl.service';
import { SharedDataService } from '../../services/shared-data/shared-data.service';
import { handleError } from '../../utlities/error-handling-utils';

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
          MatTabsModule,
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
     assets: any[] = [];
     errorMessage: string = '';
     displayedColumns: string[] = ['combined'];
     selectedTabIndex: number = 0;
     newAccount: any = null;
     totalItems: number = 0;
     pageSize: number = 10;
     currentPage: number = 1;
     isLoading: boolean = false;
     hasMore: boolean = true;
     isVisible: boolean = false;
     isTransactionDetails: boolean = false;
     selectedTransaction: string = '';
     isLoadingAssets: boolean = false;
     displayedColumnsAssets: string[] = ['Issuer', 'NFTokenID']; // Define columns dynamically

     constructor(
          private readonly xrplService: XrplService,
          private readonly snackBar: MatSnackBar,
          private readonly datePipe: DatePipe,
          private readonly route: ActivatedRoute,
          private readonly router: Router,
          private readonly sharedDataService: SharedDataService,
          private readonly cdr: ChangeDetectorRef
     ) { }

     ngOnInit(): void {
          console.log('Inside AccountInfoComponent ngOnInit');

          // Handle route parameters
          this.route.params.subscribe(params => {
               console.log('Route Params:', params);
               if (params['wallet_address']) {
                    this.wallet_address = params['wallet_address'];
                    this.resetState();
                    this.sharedDataService.setWalletAddress(this.wallet_address);
                    this.isVisible = true;
                    this.fetchAccountInfo(this.wallet_address);
                    this.loadMoreTransactions();
                    this.cdr.detectChanges();
               }
          });

          // Subscribe to shared service for real-time updates
          this.sharedDataService.walletAddress$.subscribe(address => {
               console.log('Wallet Address subscription triggered with:', address);
               if (address) {
                    this.wallet_address = address;
                    this.resetState();
                    this.isVisible = true;
                    this.fetchAccountInfo(this.wallet_address);
                    this.loadMoreTransactions();
                    this.cdr.detectChanges();
               } else {
                    this.isVisible = false;
                    this.cdr.detectChanges();
               }
          });

          this.sharedDataService.transactionHash$.subscribe(transactionHash => {
               this.transactionHash = transactionHash;
               console.log('Transaction Hash from Shared Service:', transactionHash);
          });
     }

     // Add resetState method to clear previous state, including assets
     private resetState(): void {
          this.transactions = [];
          this.assets = [];
          this.currentPage = 1;
          this.totalItems = 0;
          this.hasMore = true;
          this.accountInfo = null;
          this.errorMessage = '';
          this.isLoading = false;
          this.isLoadingAssets = false;
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

     fetchAccountInfo(account: string) {
          console.log('Fetching account info for:', account);
          const bodyData = {
               account: account,
          };

          this.xrplService.getAccountInfo(account, bodyData).subscribe({
               next: (data) => {
                    this.accountInfo = data;
                    this.errorMessage = '';
                    console.log('Account Info:', data);
                    this.cdr.detectChanges();
               },
               error: (error) => {
                    this.errorMessage = 'Error fetching account info. Please check the account ID.';
                    console.error('Error fetching account info:', error);
                    this.cdr.detectChanges();
               }
          });
     }

     loadMoreTransactions(): void {
          if (!this.hasMore || this.isLoading) {
               console.log('Skipping fetch - hasMore:', this.hasMore, 'isLoading:', this.isLoading);
               return;
          }

          this.isLoading = true;
          console.log('Fetching with page:', this.currentPage, 'pageSize:', this.pageSize);
          const bodyData = {
               account: this.wallet_address,
               page_size: this.pageSize,
               page: this.currentPage
          };
          console.log('Request body:', bodyData); // Debug request

          this.xrplService.getAccountTransactionHistoryWithPaginations(this.wallet_address, this.currentPage, this.pageSize, bodyData).subscribe({
               next: (data) => {
                    console.log('API Response:', data);
                    console.log('Transactions length:', data?.transactions?.length);
                    if (data?.transactions) {
                         const newTransactions = data.transactions.map((tx: any) => {
                              let additionalInfo: string;
                              let tx_type: string;
                              let currency: string;
                              let issuer: string;
                              let value: string;

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
                                             if (typeof tx.meta.delivered_amount === 'string') {
                                                  value = (parseInt(tx.meta.delivered_amount) / 1000000).toFixed(2);
                                                  currency = 'XRP';
                                                  issuer = tx.tx_json.Destination || 'N/A';
                                             } else {
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
                                             additionalInfo = tx.tx_json.TransactionType;
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
                         this.totalItems = data.total_count || 0; // Fix here
                         this.currentPage++;
                         this.hasMore = this.transactions.length < this.totalItems;
                         console.log('Fetch complete - Total items:', this.totalItems, 'Loaded:', this.transactions.length, 'Has more:', this.hasMore, 'Next page:', this.currentPage);
                    } else {
                         console.warn('No transactions in API response');
                         this.hasMore = false;
                    }
                    this.isLoading = false;
                    this.cdr.detectChanges();
               },
               error: (error) => {
                    console.error('Error fetching account transactions:', error);
                    handleError(error, this.snackBar, 'Creating token check', {
                         setErrorMessage: (msg) => (this.errorMessage = msg),
                         setLoading: (loading) => (this.isLoading = loading),
                    })
                    this.cdr.detectChanges();
               },
               complete: () => {
                    // Optional: Add any cleanup or finalization logic here
                    console.log('Transaction history fetch completed.');
               }
          });
     }

     onTabChange(event: MatTabChangeEvent): void {
          const index = event.index;
          console.log('Tab changed to index in onTabChange:', index); // Debug log
          this.selectedTabIndex = index;
          if (index === 1 && this.assets.length === 0) { // Assets tab (index 1)
               this.loadAssets();
          }
          this.cdr.detectChanges(); // Ensure UI updates after tab change
     }

     loadAssets(): void {
          if (!this.wallet_address || this.isLoadingAssets) return;

          const bodyData = {
               account: this.wallet_address
          };
          console.log('Request body:', bodyData);

          this.isLoadingAssets = true;
          console.log('Fetching assets for:', this.wallet_address);
          this.xrplService.getAccountAssets(this.wallet_address, bodyData).subscribe({
               next: (data) => {
                    console.log('API Response for assets:', data);

                    if (data && typeof data === 'object' && data.account_nfts) {
                         const assetsArray = data.account_nfts;
                         console.log('data.account_nfts:', assetsArray);

                         // Map to properties matching the API response
                         this.assets = assetsArray.map((asset: any) => ({
                              Issuer: asset.Issuer || 'Unknown Asset',
                              NFTokenID: asset.NFTokenID || '0',
                              // Add more properties here as needed, e.g., Flags, NFTokenTaxon, nft_serial
                         }));
                         console.log('Processed assets:', this.assets);
                    } else {
                         this.assets = [];
                    }

                    this.isLoadingAssets = false;
                    this.cdr.detectChanges();
               },
               error: (error) => {
                    this.assets = [];
                    console.error('Error fetching account assets:', error);
                    handleError(error, this.snackBar, 'Creating token check', {
                         setErrorMessage: (msg) => (this.errorMessage = msg),
                         setLoading: (loading) => (this.isLoading = loading),
                         setisLoadingAssets: (isLoadingAssets) => (this.isLoadingAssets = isLoadingAssets),
                    })
                    this.cdr.detectChanges();
               }
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
