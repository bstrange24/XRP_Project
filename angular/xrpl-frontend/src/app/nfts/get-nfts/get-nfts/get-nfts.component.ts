import { Component, OnInit, ChangeDetectorRef, HostListener } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatTableModule } from '@angular/material/table';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTabsModule, MatTabChangeEvent } from '@angular/material/tabs';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { XrplService } from '../../../services/xrpl-data/xrpl.service';
import { SharedDataService } from '../../../services/shared-data/shared-data.service';

@Component({
  selector: 'app-get-nfts',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatTableModule,
    MatTabsModule,
    RouterModule,
  ],
  templateUrl: './get-nfts.component.html',
  styleUrl: './get-nfts.component.css',
  providers: [DatePipe],
})
export class GetNftsComponent implements OnInit {
  account: string = ''; // Bound to the input field
  wallet_address: string = ''; // Internal state for the wallet address
  isLoading: boolean = false;
  totalItems: number = 0;
  pageSize: number = 10;
  currentPage: number = 1;
  hasMore: boolean = true;
  errorMessage: string = '';
  displayedColumns: string[] = ['combined'];
  transactions: any[] = [];
  selectedTabIndex: number = 0;
  isTransactionDetails: boolean = false;

  constructor(
    private readonly xrplService: XrplService,
    private readonly snackBar: MatSnackBar,
    private readonly datePipe: DatePipe,
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly sharedDataService: SharedDataService,
    private readonly cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    console.log('Inside GetNftsComponent ngOnInit');

    // Handle route parameters (but don’t load NFTs yet)
    this.route.params.subscribe(params => {
      console.log('Route Params:', params);
      if (params['wallet_address']) {
        this.account = params['wallet_address']; // Pre-fill the input field
        this.wallet_address = params['wallet_address'];
        this.sharedDataService.setWalletAddress(this.wallet_address);
        this.cdr.detectChanges();
      }
    });

    // Subscribe to shared service (but don’t load NFTs yet)
    this.sharedDataService.walletAddress$.subscribe(address => {
      console.log('Wallet Address subscription triggered with:', address);
      if (address) {
        this.account = address; // Pre-fill the input field
        this.wallet_address = address;
        this.cdr.detectChanges();
      }
    });
  }

  private resetState(): void {
    this.transactions = [];
    this.currentPage = 1;
    this.totalItems = 0;
    this.hasMore = true;
    this.errorMessage = '';
    this.isLoading = false;
  }

  onEnter(): void {
    if (this.account.trim()) {
      this.wallet_address = this.account; // Update wallet_address from input
      this.resetState();
      this.loadMoreTransactions(); // Load NFTs only when user triggers this
      this.cdr.detectChanges();
    }
  }

  onTabChange(event: MatTabChangeEvent): void {
    this.selectedTabIndex = event.index;
    this.cdr.detectChanges();
  }

  navigateToTransaction(wallet_address: string, transaction_hash: string): void {
    console.log('Navigating to:', wallet_address);
    console.log('hash:', transaction_hash);
    this.sharedDataService.setTransactionHashSubject(transaction_hash);
    this.isTransactionDetails = true;
  }

  loadMoreTransactions(): void {
    if (!this.hasMore || this.isLoading || !this.wallet_address) {
      console.log('Skipping fetch - hasMore:', this.hasMore, 'isLoading:', this.isLoading, 'wallet_address:', this.wallet_address);
      return;
    }

    this.isLoading = true;
    console.log('Fetching with page:', this.currentPage, 'pageSize:', this.pageSize);
    const bodyData = {
      account: this.wallet_address,
      page_size: this.pageSize,
      page: this.currentPage
    };
    console.log('Request body:', bodyData);

    this.xrplService.getAccountNftsWithPaginations(this.wallet_address, this.currentPage, this.pageSize, bodyData).subscribe({
      next: (data) => {
        console.log('API Response:', data);
        if (data?.transactions) {
          this.transactions = data.transactions;
          this.totalItems = data.total_count || 0;
          this.currentPage++;
          this.hasMore = this.transactions.length < this.totalItems;
          console.log('Fetch complete - Total items:', this.totalItems, 'Loaded:', this.transactions.length, 'Has more:', this.hasMore);
        } else {
          console.warn('No transactions in API response');
          this.hasMore = false;
        }
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: (error) => {
        console.error('Error fetching account transactions:', error);
        this.errorMessage = 'Error fetching NFTs. Please try again.';
        this.isLoading = false;
        this.hasMore = false;
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
}
// import { Component, OnInit, ChangeDetectorRef, HostListener } from '@angular/core';
// import { CommonModule, DatePipe } from '@angular/common';
// import { FormsModule } from '@angular/forms';
// import { MatCardModule } from '@angular/material/card';
// import { MatFormFieldModule } from '@angular/material/form-field';
// import { MatInputModule } from '@angular/material/input';
// import { MatButtonModule } from '@angular/material/button';
// import { MatExpansionModule } from '@angular/material/expansion';
// import { MatTableModule } from '@angular/material/table';
// import { MatSnackBar } from '@angular/material/snack-bar';
// import { MatToolbarModule } from '@angular/material/toolbar';
// import { MatMenuModule } from '@angular/material/menu';
// import { MatSelectModule } from '@angular/material/select';
// import { MatOptionModule } from '@angular/material/core';
// import { MatIconModule } from '@angular/material/icon';
// import { MatTabsModule, MatTabChangeEvent } from '@angular/material/tabs';
// import { RouterModule, ActivatedRoute, Router } from '@angular/router';
// import { XrplService } from '../../../services/xrpl-data/xrpl.service';
// import { SharedDataService } from '../../../services/shared-data/shared-data.service';

// @Component({
//      selector: 'app-get-nfts',
//      standalone: true,
//      imports: [
//           CommonModule,
//           FormsModule,
//           MatCardModule,
//           MatFormFieldModule,
//           MatInputModule,
//           MatButtonModule,
//           MatExpansionModule,
//           MatTableModule,
//           MatToolbarModule,
//           MatMenuModule,
//           MatSelectModule,
//           MatOptionModule,
//           MatIconModule,
//           MatTabsModule,
//           RouterModule,
//      ],
//      templateUrl: './get-nfts.component.html',
//      styleUrl: './get-nfts.component.css',
//      providers: [DatePipe],
// })
// export class GetNftsComponent implements OnInit {
//      wallet_address: string = '';
//      isLoading: boolean = false;
//      totalItems: number = 0;
//      pageSize: number = 10;
//      currentPage: number = 1;
//      hasMore: boolean = true;
//      isVisible: boolean = false;
//      errorMessage: string = '';
//      displayedColumns: string[] = ['combined'];
//      transactions: any[] = [];
//      assets: any[] = [];
//      isLoadingAssets: boolean = false;
//      account: string = '';
//      selectedTabIndex: number = 0;
//      isTransactionDetails: boolean = false;

//      constructor(
//           private readonly xrplService: XrplService,
//           private readonly snackBar: MatSnackBar,
//           private readonly datePipe: DatePipe,
//           private readonly route: ActivatedRoute,
//           private readonly router: Router,
//           private readonly sharedDataService: SharedDataService,
//           private readonly cdr: ChangeDetectorRef
//      ) { }

//      ngOnInit(): void {
//           console.log('Inside GetNftsComponent ngOnInit');

//           // Handle route parameters
//           this.route.params.subscribe(params => {
//                console.log('Route Params:', params);
//                if (params['wallet_address']) {
//                     this.wallet_address = params['wallet_address'];
//                     this.resetState();
//                     this.sharedDataService.setWalletAddress(this.wallet_address);
//                     this.isVisible = true;
//                     this.loadMoreTransactions();
//                     this.cdr.detectChanges();
//                }
//           });
//           // Subscribe to shared service for real-time updates
//           this.sharedDataService.walletAddress$.subscribe(address => {
//                console.log('Wallet Address subscription triggered with:', address);
//                if (address) {
//                     this.wallet_address = address;
//                     this.resetState();
//                     this.isVisible = true;
//                     this.loadMoreTransactions();
//                     this.cdr.detectChanges();
//                } else {
//                     this.isVisible = false;
//                     this.cdr.detectChanges();
//                }
//           });
//      }

//      private resetState(): void {
//           this.transactions = [];
//           this.assets = [];
//           this.currentPage = 1;
//           this.totalItems = 0;
//           this.hasMore = true;
//           this.errorMessage = '';
//           this.isLoading = false;
//           this.isLoadingAssets = false;
//      }

//      onEnter(): void {
//           if (this.wallet_address.trim()) {
//                this.transactions = [];
//                this.currentPage = 1;
//                this.hasMore = true;
//                // this.loadMoreTransactions();
//                this.isVisible = true;
//           }
//      }

//      onTabChange(event: MatTabChangeEvent): void {
//           const index = event.index;
//           console.log('Tab changed to index in onTabChange:', index); // Debug log
//           this.selectedTabIndex = index;
//           if (index === 1 && this.assets.length === 0) { // Assets tab (index 1)
//                // this.loadAssets();
//           }
//           this.cdr.detectChanges(); // Ensure UI updates after tab change
//      }

//      navigateToTransaction(wallet_address: string, transaction_hash: string): void {
//           console.log('Navigating to:', wallet_address);
//           console.log('hash:', transaction_hash);
//           this.sharedDataService.setTransactionHashSubject(transaction_hash);
//           this.isTransactionDetails = true;
//           // this.router.navigate(['/transaction']);
//      }

//      // loadAssets(): void {
//      //      if (!this.wallet_address || this.isLoadingAssets) return;

//      //      const bodyData = {
//      //           account: this.wallet_address
//      //      };
//      //      console.log('Request body:', bodyData); 

//      //      this.isLoadingAssets = true;
//      //      console.log('Fetching assets for:', this.wallet_address);
//      //      this.xrplService.getAccountAssets(this.wallet_address, bodyData).subscribe({
//      //           next: (data) => {
//      //                console.log('API Response for assets:', data);

//      //                if (data && typeof data === 'object' && data.account_nfts) {
//      //                     const assetsArray = data.account_nfts;
//      //                     console.log('data.account_nfts:', assetsArray);

//      //                     // Map to properties matching the API response
//      //                     this.assets = assetsArray.map((asset: any) => ({
//      //                          Issuer: asset.Issuer || 'Unknown Asset',
//      //                          NFTokenID: asset.NFTokenID || '0',
//      //                          // Add more properties here as needed, e.g., Flags, NFTokenTaxon, nft_serial
//      //                     }));
//      //                     console.log('Processed assets:', this.assets);
//      //                } else {
//      //                     this.assets = [];
//      //                }

//      //                this.isLoadingAssets = false;
//      //                this.cdr.detectChanges();
//      //           },
//      //           error: (error) => {
//      //                console.error('Error fetching account assets:', error);
//      //                this.errorMessage = 'Error fetching account assets. Please try again.';
//      //                this.assets = [];
//      //                this.isLoadingAssets = false;
//      //                this.cdr.detectChanges();
//      //           }
//      //      });
//      // }

//      loadMoreTransactions(): void {
//           if (!this.hasMore || this.isLoading) {
//                console.log('Skipping fetch - hasMore:', this.hasMore, 'isLoading:', this.isLoading);
//                return;
//           }

//           this.isLoading = true;
//           console.log('Fetching with page:', this.currentPage, 'pageSize:', this.pageSize);
//           const bodyData = {
//                account: this.wallet_address,
//                page_size: this.pageSize,
//                page: this.currentPage
//           };
//           console.log('Request body:', bodyData); // Debug request

//           this.xrplService.getAccountNftsWithPaginations(this.wallet_address, this.currentPage, this.pageSize, bodyData).subscribe({
//                next: (data) => {
//                     console.log('API Response:', data);
//                     console.log('Transactions length:', data?.transactions?.length);
//                     if (data?.transactions) {
//                          this.transactions = data?.transactions;
//                          this.totalItems = data.total_count || 0; // Fix here
//                          this.currentPage++;
//                          this.hasMore = this.transactions.length < this.totalItems;
//                          console.log('Fetch complete - Total items:', this.totalItems, 'Loaded:', this.transactions.length, 'Has more:', this.hasMore, 'Next page:', this.currentPage);
//                     } else {
//                          console.warn('No transactions in API response');
//                          this.hasMore = false;
//                     }
//                     this.isLoading = false;
//                     this.cdr.detectChanges();
//                },
//                error: (error) => {
//                     console.error('Error fetching account transactions:', error);
//                     this.isLoading = false;
//                     this.hasMore = false;
//                     this.cdr.detectChanges();
//                },
//                complete: () => {
//                     // Optional: Add any cleanup or finalization logic here
//                     console.log('Transaction history fetch completed.');
//                }
//           });
//      }

//      @HostListener('wheel', ['$event'])
//      onWheel(event: WheelEvent): void {
//           const element = document.querySelector('.table-container');
//           if (element) {
//                const atBottom = element.scrollTop + element.clientHeight >= element.scrollHeight - 50;
//                if (event.deltaY > 0 && atBottom && !this.isLoading && this.hasMore) {
//                     this.loadMoreTransactions();
//                }
//           }
//      }

//      getTransactionProperty(tx: any, property: string): string {
//           return tx?.tx?.[property] || 'N/A';
//      }

//      objectKeys(obj: any): string[] {
//           return Object.keys(obj);
//      }

//      convertDropsToXrp(drops: string | number): number {
//           return Number(drops) / 1000000;
//      }
// }

