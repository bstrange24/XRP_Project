import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpParams } from '@angular/common/http';
import * as XRPL from 'xrpl';
import { firstValueFrom } from 'rxjs';
import { WalletService } from '../services/wallet-services/wallet.service';

// Define the interface for the API response
interface AccountConfigResponse {
  status: string;
  message: string;
  result: {
    account_data: {
      Account: string;
      AccountTxnID: string;
      Balance: string;
      Flags: number;
      LedgerEntryType: string;
      OwnerCount: number;
      PreviousTxnID: string;
      PreviousTxnLgrSeq: number;
      Sequence: number;
      index: string;
    };
    account_flags: {
      allowTrustLineClawback: boolean;
      defaultRipple: boolean;
      depositAuth: boolean;
      disableMasterKey: boolean;
      disallowIncomingCheck: boolean;
      disallowIncomingNFTokenOffer: boolean;
      disallowIncomingPayChan: boolean;
      disallowIncomingTrustline: boolean;
      disallowIncomingXRP: boolean;
      globalFreeze: boolean;
      noFreeze: boolean;
      passwordSpent: boolean;
      requireAuthorization: boolean;
      requireDestinationTag: boolean;
    };
    ledger_hash: string;
    ledger_index: number;
    validated: boolean;
  };
}

interface XamanWalletData {
  address: string;
  seed?: string; // Optional, as Xaman doesn’t expose seeds
}

@Component({
  selector: 'app-get-account-config',
  standalone: true,
  imports: [CommonModule, FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  templateUrl: './get-account-config.component.html',
  styleUrls: ['./get-account-config.component.css']
})
export class GetAccountConfigComponent implements OnInit {
  account: string = '';
  accountFlags: { [key: string]: boolean } | null = null; // Store account_flags
  balance: string | null = null; // Store Balance
  isLoading: boolean = false;
  errorMessage: string = '';
  connectedWallet: XamanWalletData | null = null;

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient,
    private readonly walletService: WalletService
  ) {}

  // Validate XRP wallet address using xrpl
  private isValidXrpAddress(address: string): boolean {
    if (!address || typeof address !== 'string') return false;
    
    try {
      return XRPL.isValidAddress(address.trim());
    } catch (error) {
      console.error('Error validating XRP address:', error);
      return false;
    }
  }

  ngOnInit(): void {
     // Get the wallet from the service when the component initializes
     this.connectedWallet = this.walletService.getWallet();
     if (this.connectedWallet) {
       this.account = this.connectedWallet.address;
     } else {
      console.log('No wallet is connected. We need to get the user to input one.')
     }
    // Optionally pre-load with a default or empty state
  }

  async getAccountConfig(): Promise<void> {
    this.isLoading = true;
    this.errorMessage = '';
    this.accountFlags = null;
    this.balance = null;

    if (!this.account.trim() || !this.isValidXrpAddress(this.account)) {
      this.snackBar.open('Please enter a valid XRP account address.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }

    try {
      const response = await firstValueFrom(this.http.get<AccountConfigResponse>(`http://127.0.0.1:8000/xrpl/get-account-config/${this.account.trim()}/`));
      this.accountFlags = response.result.account_flags;
      this.balance = response.result.account_data.Balance;
      this.isLoading = false;
      console.log('Account config retrieved:', response);
    } catch (error: any) {
      console.error('Error retrieving account config:', error);
      let errorMessage: string;
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error as any).message;
      } else {
        errorMessage = 'An unexpected error occurred while retrieving account config.';
      }
      this.errorMessage = errorMessage;
      this.snackBar.open(this.errorMessage, 'Close', {
        duration: 3000,
        panelClass: ['error-snackbar']
      });
      this.isLoading = false;
    }
  }

  // Helper method to get entries safely
  getEntries(obj: { [key: string]: boolean } | null): [string, boolean][] {
    return obj ? Object.entries(obj) as [string, boolean][] : [];
  }
}