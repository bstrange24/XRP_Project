import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { WalletService } from '../../services/wallet-services/wallet.service';
import { ValidationUtils } from '../../utlities/validation-utils';
import { handleError } from '../../utlities/error-handling-utils';

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
     ) { }

     ngOnInit(): void {
          // Get the wallet from the service when the component initializes
          this.connectedWallet = this.walletService.getWallet();
          if (this.connectedWallet) {
               this.account = this.connectedWallet.address;
          } else {
               console.log('No wallet is connected. We need to get the user to input one.')
          }
     }

     async getAccountConfig(): Promise<void> {
          this.isLoading = true;
          this.errorMessage = '';
          this.accountFlags = null;
          this.balance = null;

          if (!this.account.trim() || !ValidationUtils.isValidXrpAddress(this.account)) {
               this.snackBar.open('Please enter a valid XRP account address.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               this.isLoading = false;
               return;
          }

          console.log('I:M HERE 1-----------------------')

          try {
               const bodyData = {
                    account: this.account.trim(),
               };

               const headers = new HttpHeaders({
                    'Content-Type': 'application/json',
               });

               const response = await firstValueFrom(
                    this.http.post<AccountConfigResponse>(
                         'http://127.0.0.1:8000/xrpl/account/config/',
                         bodyData,
                         { headers }
                    )
               );

               this.accountFlags = response.result.account_flags;
               this.balance = response.result.account_data.Balance;
               this.isLoading = false;
               console.log('Account config retrieved:', response);
          } catch (error: any) {
               console.error('Error retrieving account config:', error);
               handleError(error, this.snackBar, 'Creating token check', {
                    setErrorMessage: (msg) => (this.errorMessage = msg),
                    setLoading: (loading) => (this.isLoading = loading),
               })
          }
     }

     // Helper method to get entries safely
     getEntries(obj: { [key: string]: boolean } | null): [string, boolean][] {
          return obj ? Object.entries(obj) : [];
     }
}