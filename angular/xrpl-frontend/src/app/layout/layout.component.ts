import { Component, OnInit, ChangeDetectorRef, ViewChild } from '@angular/core';
import { CommonModule, } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatDialog } from '@angular/material/dialog';
import { MatTableModule } from '@angular/material/table';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatMenuModule } from '@angular/material/menu';
import { MatSelectModule } from '@angular/material/select';
import { MatOptionModule } from '@angular/material/core';
import { MatIconModule } from '@angular/material/icon';
import { RouterModule, Router } from '@angular/router';
import { SharedDataService } from '../services/shared-data/shared-data.service';
import { HttpClient } from '@angular/common/http';
import * as XRPL from 'xrpl';
import { firstValueFrom } from 'rxjs';
import { ConnectWalletComponent } from '../connect-wallet/connect-wallet.component';
import { WalletService } from '../services/wallet-services/wallet.service';
import { MatSidenav } from '@angular/material/sidenav'; 
import { MatSidenavModule } from '@angular/material/sidenav';
import { MediaMatcher } from '@angular/cdk/layout';

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
    MatSidenav,
    MatSidenavModule,
    MatIconModule,
    RouterModule,
  ],
  templateUrl: './layout.component.html',
  styleUrls: ['./layout.component.css']
})
export class LayoutComponent implements OnInit {
  user_search_input: string = '';
  walletConnected: boolean = false;
  walletAddress: string = '';
  wallet_address: string = '';
  ledger_index: string = '';
  isVisible = false;
  private isDisconnecting: boolean = false;
  @ViewChild('sidenav') sidenav?: MatSidenav;
  private readonly mobileQuery: MediaQueryList;
  private readonly mobileQueryListener: () => void;

  constructor(
    private readonly router: Router,
    private readonly sharedDataService: SharedDataService,
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient,
    private readonly dialog: MatDialog,
    private readonly walletService: WalletService,
    private readonly cdr: ChangeDetectorRef,
    media: MediaMatcher,
  ) {
    this.mobileQuery = media.matchMedia('(max-width: 768px)');
    this.mobileQueryListener = () => this.updateSidenavMode();
    this.mobileQuery.addEventListener('change', this.mobileQueryListener);
    this.walletService.wallet$.subscribe(wallet => {
      this.walletConnected = !!wallet;
      this.walletAddress = wallet?.address || '';
      this.cdr.detectChanges();
    });
  }

  ngOnInit(): void {
    // Restore user_search_input from sessionStorage
    const savedSearch = sessionStorage.getItem('userSearchInput');
    if (savedSearch) {
      this.user_search_input = savedSearch;
      console.log('Restored search input from sessionStorage:', this.user_search_input);
      this.onEnter(); // Trigger search on load if input exists
    }

    const currentWallet = this.walletService['walletSubject'].getValue();
    if (currentWallet) {
      this.walletConnected = true;
      this.walletAddress = currentWallet.address || '';
    } else {
      const storedWallet = sessionStorage.getItem('xamanWallet');
      if (storedWallet) {
        const wallet = JSON.parse(storedWallet);
        this.walletService.setWallet(wallet);
        this.walletConnected = true;
        this.walletAddress = wallet.address || '';
      }
    }

    this.cdr.detectChanges();

    console.log('Initial state in LayoutComponent:', {
      walletConnected: this.walletConnected,
      walletAddress: this.walletAddress
    });

    this.walletService.wallet$.subscribe(wallet => {
      this.walletConnected = !!wallet;
      this.walletAddress = wallet?.address ?? '';
      this.cdr.detectChanges();
      console.log('Wallet updated in LayoutComponent:', {
        walletConnected: this.walletConnected,
        walletAddress: this.walletAddress
      });
    });
  }

  ngOnDestroy(): void {
    this.mobileQuery.removeEventListener('change', this.mobileQueryListener);
  }

  toggleSidenav(): void {
    if (this.sidenav) {
      if (this.mobileQuery.matches) {
        // Mobile: Toggle visibility using MatSidenav's opened state
        this.sidenav.toggle();
        this.cdr.detectChanges(); // Ensure UI updates
      } else {
        // Desktop: Use standard toggle for side mode
        this.sidenav.toggle();
      }
    }
  }

  private updateSidenavMode(): void {
    if (this.sidenav) {
      this.sidenav.mode = this.mobileQuery.matches ? 'over' : 'side';
      this.sidenav.opened = !this.mobileQuery.matches; // Open by default on desktop, closed on mobile
      this.cdr.detectChanges();
    }
  }

  private isValidXrpAddress(address: string): boolean {
    if (!address || typeof address !== 'string') return false;

    try {
      return XRPL.isValidAddress(address.trim());
    } catch (error) {
      console.error('Error validating XRP address:', error);
      return false;
    }
  }

  private async isValidLedgerIndex(ledgerIndex: number): Promise<boolean> {
    try {
	  const client = new XRPL.Client('wss://s1.ripple.com');
      await client.connect();
      const response = await client.request({
        command: 'ledger',
        ledger_index: ledgerIndex,
        transactions: false,
        expand: false,
      });
      await client.disconnect();
      return response.result.validated === true;
    } catch (error) {
      console.error('Error validating ledger index:', error);
      return false;
    }
  }

  private isSyntacticallyValidLedgerIndex(index: string | number): boolean {
    const num = Number(index);
    return Number.isInteger(num) && num > 0 && num <= 4294967295;
  }

  async onEnter(): Promise<void> {
    const userInput = this.user_search_input.trim();
    console.log('User input:', userInput);
    // Save user input to sessionStorage
    sessionStorage.setItem('userSearchInput', userInput);
  
    if (userInput) {
      if (this.isValidXrpAddress(userInput)) {
        this.wallet_address = userInput;
        this.sharedDataService.setWalletAddress(this.wallet_address);
        this.isVisible = true; // Set in LayoutComponent to ensure immediate state
        this.cdr.detectChanges();
        console.log('Navigating to account-info with wallet:', this.wallet_address);
        this.router.navigate(['/account-info', this.wallet_address]).then(() => {
          console.log('Navigation completed to /account-info/', this.wallet_address);
        });
      } else if (this.isSyntacticallyValidLedgerIndex(userInput)) {
        const ledgerIndexNum = Number(userInput);
        console.log('Validating ledger index:', ledgerIndexNum);
        const isValid = await this.isValidLedgerIndex(ledgerIndexNum);
        if (isValid) {
          this.ledger_index = userInput;
          this.sharedDataService.setLedgerIndex(this.ledger_index);
          this.cdr.detectChanges();
          console.log('Navigating to get-ledger-info with ledger index:', this.ledger_index);
          this.router.navigate(['/get-ledger-info', this.ledger_index]).then(() => {
            console.log('Navigation completed to /get-ledger-info/', this.ledger_index);
          });
        } else {
          this.snackBar.open('Ledger not found on the XRPL', 'Close', {
            duration: 3000,
            panelClass: ['error-snackbar']
          });
          console.log('Ledger validation failed for index:', ledgerIndexNum);
          return;
        }
      } else {
        this.snackBar.open('Invalid input. Please enter a valid XRP wallet address or ledger index.', 'Close', {
          duration: 3000,
          panelClass: ['error-snackbar']
        });
        console.log('Invalid input:', userInput);
        return;
      }
    } else {
      this.snackBar.open('Please enter a wallet address or ledger index.', 'Close', {
        duration: 3000,
        panelClass: ['error-snackbar']
      });
      console.log('Empty input');
    }
    this.cdr.detectChanges(); // Force UI update after navigation
  }

  async createNewWallet(): Promise<void> {
    this.isVisible = true;
    try {
      const response = await firstValueFrom(this.http.get('http://127.0.0.1:8000/xrpl/create-test-account/'));
      console.log('New account created:', response);
      this.sharedDataService.setNewAccount(response);
      this.router.navigate(['/create-account']);
    } catch (error: any) {
      console.error('Error creating test account:', error);
      let errorMessage: string;
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error).message;
      } else {
        errorMessage = 'An unexpected error occurred while creating the wallet.';
      }
      this.snackBar.open(errorMessage, 'Close', {
        duration: 3000,
        panelClass: ['error-snackbar']
      });
    }
  }

  openConnectWalletDialog(): void {
    if (this.walletConnected) {
      this.snackBar.open('Wallet already connected. Disconnect first.', 'Close', { duration: 3000 });
      return;
    }
    console.log('Opening Connect Wallet dialog. Current state:', {
      walletConnected: this.walletConnected,
      walletAddress: this.walletAddress
    });

    const dialogRef = this.dialog.open(ConnectWalletComponent, {
      width: '700px', // Adjust size as needed
    });

    dialogRef.afterClosed().subscribe(result => {
      console.log('Dialog closed with result:', result);
      if (result && result.connected) {
      }
    });
  }

  disconnectWallet(): void {
    if (this.isDisconnecting) return;
    this.isDisconnecting = true;
    try {
      this.walletService.setWallet(null);
      this.cdr.detectChanges();
    } finally {
      this.isDisconnecting = false;
    }
  }

  // Navigate to Create Trust Line page
  navigateToCreateTrustLine() {
    this.router.navigate(['/create-trust-line']);
  }

  // Navigate to Remove Trust Line page
  navigateToRemoveTrustLine() {
    this.router.navigate(['/remove-trust-line']);
  }

  // Navigate to Send Payment page
  navigateToSendPayment() {
    this.router.navigate(['/send-payment']);
  }

  // Navigate to Send Payment and Delete Account page
  navigateToSendPaymentAndDeleteAccount() {
    this.router.navigate(['/send-payment-and-delete-account']);
  }

  // Navigate to Send Payment and Black Hole Account page
  navigateToSendPaymentAndBlackHoleAccount() {
    this.router.navigate(['/send-payment-and-black-hole-account']);
  }

  // Navigate to Send Currency Payment page
  navigateToSendCurrencyPayment() {
    this.router.navigate(['/send-currency-payment']);
  }

  // Navigate to Get Trust Lines page
  navigateToGetTrustLines() {
    this.router.navigate(['/get-trust-lines']);
  }

  // Navigate to Get Account Offers page
  navigateToGetAccountOffers() {
    this.router.navigate(['/get-account-offers']);
  }

  // Navigate to Cancel Account Offers page
  navigateToCancelAccountOffers() {
    this.router.navigate(['/cancel-account-offers']);
  }

  // Navigate to Get Server Info page
  navigateToGetServerInfo() {
    this.router.navigate(['/get-server-info']);
  }

  // Navigate to Get Account Config page
  navigateToGetAccountConfig() {
    this.router.navigate(['/get-account-config']);
  }

  // Navigate to Update Account Config page
  navigateToUpdateAccountConfig() {
    this.router.navigate(['/update-account-config']);
  }

  // Navigate to Connect Wallet page
  navigateToConnectWallet() {
    this.router.navigate(['/connect-wallet']);
  }

  navigateToHome() {
    this.router.navigate(['']);
  }
}