import { Component, ViewEncapsulation, OnInit } from '@angular/core';
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
import { HttpClient } from '@angular/common/http'; // Import HttpClient
import * as XRPL from 'xrpl';
import { firstValueFrom } from 'rxjs'; // Import for modern RxJS usage


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
  user_search_input: string = '';
  wallet_address: string = '';
  ledger_index: string = '';
  isVisible = false;

  constructor(
    private readonly router: Router, 
    private readonly sharedDataService: SharedDataService,
    private readonly snackBar: MatSnackBar, // Inject MatSnackBar for error messages
    private readonly http: HttpClient // Inject HttpClient
  ) {}

  // Function to validate XRP wallet address using xrpl
  private isValidXrpAddress(address: string): boolean {
    if (!address || typeof address !== 'string') return false;
    
    try {
      // Use xrpl's isValidAddress function to validate the XRP address
      return XRPL.isValidAddress(address.trim());
    } catch (error) {
      console.error('Error validating XRP address:', error);
      return false;
    }
  }

  // Async function to validate ledger index using xrpl
  private async isValidLedgerIndex(ledgerIndex: number): Promise<boolean> {
    try {
      const client = new XRPL.Client('wss://s1.ripple.com'); // Example WebSocket endpoint
      await client.connect();
      const response = await client.request({
        command: 'ledger',
        ledger_index: ledgerIndex,
        transactions: false,
        expand: false,
      });
      await client.disconnect();
      return response.result.validated === true; // Check if the ledger is validated
    } catch (error) {
      console.error('Error validating ledger index:', error);
      return false;
    }
  }

  // Function to check if the ledger index is syntactically valid
  private isSyntacticallyValidLedgerIndex(index: string | number): boolean {
    const num = Number(index);
    return Number.isInteger(num) && num > 0 && num <= 4294967295; // 32-bit unsigned integer max
  }
  
  // In LayoutComponent.onEnter()
  async onEnter(): Promise<void> {
    const userInput = this.user_search_input.trim();
    console.log('User input:', userInput);
  
    if (userInput) {
      // Validate if it's a valid XRP wallet address
      if (this.isValidXrpAddress(userInput)) {
        this.wallet_address = userInput;
        this.sharedDataService.setWalletAddress(this.wallet_address);
        this.isVisible = true;
        console.log('Navigating to account-info with wallet:', this.wallet_address);
        this.router.navigate(['/account-info', this.wallet_address]);
      } else if (this.isSyntacticallyValidLedgerIndex(userInput)) {
        const ledgerIndexNum = Number(userInput);
        console.log('Validating ledger index:', ledgerIndexNum);
        const isValid = await this.isValidLedgerIndex(ledgerIndexNum); // Await the async call
        if (isValid) {
          this.ledger_index = userInput;
          this.sharedDataService.setLedgerIndex(this.ledger_index);
          console.log('Navigating to get-ledger-info with ledger index:', this.ledger_index);
          this.router.navigate(['/get-ledger-info', this.ledger_index]); // Ensure this matches app.routes.ts
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
  }

// Create a new wallet directly and navigate to the result
async createNewWallet(): Promise<void> {
  this.isVisible = true;
  try {
    const response = await firstValueFrom(this.http.get('http://127.0.0.1:8000/xrpl/create-test-account/'));
    console.log('New account created:', response);
    this.sharedDataService.setNewAccount(response); // Store in service
    this.router.navigate(['/create-account']);
  } catch (error: any) {
    // ... (same error handling as before)
    console.error('Error creating test account:', error);
    let errorMessage: string;
    if (error instanceof Error) {
      errorMessage = error.message;
    } else if (typeof error === 'object' && error !== null && 'message' in error) {
      errorMessage = (error as any).message;
    } else {
      errorMessage = 'An unexpected error occurred while creating the wallet.';
    }
    this.snackBar.open(errorMessage, 'Close', {
      duration: 3000,
      panelClass: ['error-snackbar']
    });
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

navigateToHome() {
  this.router.navigate(['']);
}
}