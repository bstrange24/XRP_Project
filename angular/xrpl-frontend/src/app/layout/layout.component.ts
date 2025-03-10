import { Component, OnInit, ChangeDetectorRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
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
import { ValidationUtils } from '../utlities/validation-utils';

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
          MatSidenavModule, // Fixed: Use MatSidenavModule, not MatSidenav directly
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
          media: MediaMatcher
     ) {
          this.mobileQuery = media.matchMedia('(max-width: 768px)');
          this.mobileQueryListener = () => this.updateSidenavMode();
          this.mobileQuery.addEventListener('change', this.mobileQueryListener);

          // Single subscription in constructor
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

     ngOnInit(): void {
          // Restore user_search_input from sessionStorage
          const savedSearch = sessionStorage.getItem('userSearchInput');
          if (savedSearch) {
               this.user_search_input = savedSearch;
               console.log('Restored search input from sessionStorage:', this.user_search_input);
               this.onEnter();
          }

          // Check initial wallet state
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

          // No duplicate subscription here
     }

     ngOnDestroy(): void {
          this.mobileQuery.removeEventListener('change', this.mobileQueryListener);
     }

     toggleSidenav(): void {
          if (this.sidenav) {
               this.sidenav.toggle();
               this.cdr.detectChanges();
          }
     }

     private updateSidenavMode(): void {
          if (this.sidenav) {
               this.sidenav.mode = this.mobileQuery.matches ? 'over' : 'side';
               this.sidenav.opened = !this.mobileQuery.matches;
               this.cdr.detectChanges();
          }
     }

     // private isValidXrpAddress(address: string): boolean {
     //      if (!address || typeof address !== 'string') return false;
     //      try {
     //           return XRPL.isValidAddress(address.trim());
     //      } catch (error) {
     //           console.error('Error validating XRP address:', error);
     //           return false;
     //      }
     // }

     // private async isValidLedgerIndex(ledgerIndex: number): Promise<boolean> {
     //      try {
     //           const client = new XRPL.Client('wss://s1.ripple.com');
     //           await client.connect();
     //           const response = await client.request({
     //                command: 'ledger',
     //                ledger_index: ledgerIndex,
     //                transactions: false,
     //                expand: false,
     //           });
     //           await client.disconnect();
     //           return response.result.validated === true;
     //      } catch (error) {
     //           console.error('Error validating ledger index:', error);
     //           return false;
     //      }
     // }

     // private isSyntacticallyValidLedgerIndex(index: string | number): boolean {
     //      const num = Number(index);
     //      return Number.isInteger(num) && num > 0 && num <= 4294967295;
     // }

     async onEnter(): Promise<void> {
          const userInput = this.user_search_input.trim();
          console.log('User input:', userInput);
          sessionStorage.setItem('userSearchInput', userInput);

          if (userInput) {
               if (ValidationUtils.isValidXrpAddress(userInput)) {
                    this.wallet_address = userInput;
                    this.sharedDataService.setWalletAddress(this.wallet_address);
                    this.isVisible = true;
                    this.cdr.detectChanges();
                    // console.log('Navigating to account-info with wallet:', this.wallet_address);
                    // this.router.navigate(['/account-info', this.wallet_address]).then(() => {
                         // console.log('Navigation completed to /account-info/', this.wallet_address);
                    // });
               } else if (ValidationUtils.isSyntacticallyValidLedgerIndex(userInput)) {
                    const ledgerIndexNum = Number(userInput);
                    console.log('Validating ledger index:', ledgerIndexNum);
                    const isValid = await ValidationUtils.isValidLedgerIndex(ledgerIndexNum);
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
                    }
               } else {
                    this.snackBar.open('Invalid input. Please enter a valid XRP wallet address or ledger index.', 'Close', {
                         duration: 3000,
                         panelClass: ['error-snackbar']
                    });
                    console.log('Invalid input:', userInput);
               }
          } else {
               this.snackBar.open('Please enter a wallet address or ledger index.', 'Close', {
                    duration: 3000,
                    panelClass: ['error-snackbar']
               });
               console.log('Empty input');
          }
          this.cdr.detectChanges();
     }

     async createNewWallet(): Promise<void> {
          this.isVisible = true;
          try {
               const response = await firstValueFrom(this.http.get('http://127.0.0.1:8000/xrpl/account/create/test-account/'));
               console.log('New account created:', response);
               this.sharedDataService.setNewAccount(response);
               this.router.navigate(['/create-account']);
          } catch (error: any) {
               console.error('Error creating test account:', error);
               this.snackBar.open('An unexpected error occurred while creating the wallet.', 'Close', {
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
               width: '700px',
          });

          dialogRef.afterClosed().subscribe(result => {
               console.log('Dialog closed with result:', result);
               if (result && result.connected) {
                    // Wallet connection handled by WalletService
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

     // Navigation methods (unchanged)
     navigateToCreateTrustLine() { this.router.navigate(['/create-trust-line']); }
     navigateToRemoveTrustLine() { this.router.navigate(['/remove-trust-line']); }
     navigateToSendPayment() { this.router.navigate(['/send-payment']); }
     navigateToSendPaymentAndDeleteAccount() { this.router.navigate(['/send-payment-and-delete-account']); }
     navigateToSendPaymentAndBlackHoleAccount() { this.router.navigate(['/send-payment-and-black-hole-account']); }
     navigateToSendCurrencyPayment() { this.router.navigate(['/send-currency-payment']); }
     navigateToGetTrustLines() { this.router.navigate(['/get-trust-lines']); }
     
     navigateToGetAccountOffers() { this.router.navigate(['/get-account-offers']); }
     navigateToCancelAccountOffers() { this.router.navigate(['/cancel-account-offers']); }
     navigateToCreateOffer() { this.router.navigate(['/create-account-offers']); }
     navigateToGetBookOffers(){ this.router.navigate(['/get-book-offers']); }

     navigateToGetServerInfo() { this.router.navigate(['/get-server-info']); }
     navigateToGetLedgerInfo() { this.router.navigate(['/get-ledger-info']); }
     navigateToGetAccountConfig() { this.router.navigate(['/get-account-config']); }
     navigateToUpdateAccountConfig() { this.router.navigate(['/update-account-config']); }
     navigateToConnectWallet() { this.router.navigate(['/connect-wallet']); }

     navigateToGetAccountNfts(){ this.router.navigate(['/get-nfts']); }
     navigateToMintNfts(){ this.router.navigate(['/mint-nfts']); }
     navigateToCancelNftsSellOffer(){ this.router.navigate(['/cancel-nfts']); }
     navigateToBuyNfts(){ this.router.navigate(['/buy-nfts']); }
     navigateToSellNfts(){ this.router.navigate(['/sell-nfts']); }
     navigateToBurnNfts(){ this.router.navigate(['/burn-nfts']); }


     navigateToGetAccountChecks(){ this.router.navigate(['/get-checks']); }
     navigateToCreateTokenCheck(){ this.router.navigate(['/create_token-check']); }
     navigateToCreateXrpCheck(){ this.router.navigate(['/create_xrp-check']); }
     navigateToCashTokenCheck(){ this.router.navigate(['/cash-token-check']); }
     navigateToCashXrpCheck(){ this.router.navigate(['/cash-xrp-check']); }
     navigateToCancelCheck(){ this.router.navigate(['/cancel-check']); }

     
     navigateToGetPriceOracle(){ this.router.navigate(['/get-price-oracle']); }
     navigateToCreatePriceOracle(){ this.router.navigate(['/create-price-oracle']); }
     navigateToDeletePriceOracle(){ this.router.navigate(['/delete-price-oracle']); }
     navigateToGetAccountDid(){ this.router.navigate(['/get-account-did']); }
     navigateToSetDid(){ this.router.navigate(['/set-did']); }
     navigateToDeleteDid(){ this.router.navigate(['/delete-did']); }
     navigateToGetAccountEscrow(){ this.router.navigate(['/get-account-escrow']); }
     navigateToCreateEscrow(){ this.router.navigate(['/create-escrow']); }
     navigateToCancelEscrow(){ this.router.navigate(['/cancel-escrow']); }
     navigateToFinish(){ this.router.navigate(['/finish-escrow']); }
     navigateToHome() { this.router.navigate(['']); }
}