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
import * as XRPL from 'xrpl';
import { handleError } from '../../utlities/error-handling-utils';
import { ValidationUtils } from '../../utlities/validation-utils';
import { CalculationUtils } from '../../utlities/calculation-utils';

interface SendMax {
     currency: string;
     issuer: string;
     value: string;
}

interface TxJson {
     Account: string;
     CheckID: string; // Expected for CheckCash
     Amount: SendMax; // Token amount cashed
     Fee: string;
     Flags: number;
     LastLedgerSequence: number;
     Sequence: number;
     SigningPubKey: string;
     TransactionType: string;
     TxnSignature: string;
     date: number;
     ledger_index: number;
}

interface CashTokenCheckApiResponse {
     status: string;
     message: string;
     result: {
          close_time_iso: string;
          ctid: string;
          hash: string;
          ledger_hash: string;
          ledger_index: number;
          meta: any;
          tx_json: TxJson;
          validated: boolean;
     };
}

@Component({
     selector: 'app-cash-token-check',
     standalone: true,
     imports: [
          CommonModule,
          FormsModule,
          MatCardModule,
          MatFormFieldModule,
          MatInputModule,
          MatButtonModule,
     ],
     templateUrl: './cash-token-check.component.html',
     styleUrls: ['./cash-token-check.component.css'],
})
export class CashTokenCheckComponent implements OnInit {
     senderSeed: string = '';
     tokenName: string = '';
     tokenIssuer: string = '';
     cashAmount: string = '';
     checkId: string = '';
     isLoading: boolean = false;
     errorMessage: string = '';
     txJson: TxJson | null = null;

     constructor(
          private readonly snackBar: MatSnackBar,
          private readonly http: HttpClient
     ) { }

     ngOnInit(): void { }

     // Validate inputs before submission
     private validateInputs(): boolean {
          if (!this.senderSeed.trim()) {
               this.snackBar.open('Sender seed is required.', 'Close', { duration: 3000 });
               return false;
          }
          if (!ValidationUtils.isValidXrpSeed(this.senderSeed.trim())) {
               this.snackBar.open('Sender seed must be a valid XRP seed.', 'Close', { duration: 3000 });
               return false;
          }
          if (!ValidationUtils.isValidCurrencyCode) {
               this.snackBar.open('Token name must be a 3-character currency code.', 'Close', { duration: 3000 });
               return false;
          }
          if (!this.tokenIssuer.trim()) {
               this.snackBar.open('Token issuer is required.', 'Close', { duration: 3000 });
               return false;
          }
          if (!ValidationUtils.isValidXrpAddress(this.tokenIssuer.trim())) {
               this.snackBar.open('Token issuer must be a valid XRP address.', 'Close', { duration: 3000 });
               return false;
          }
          if (ValidationUtils.isValidAmount(this.cashAmount.trim())) {
               this.snackBar.open('Cash amount must be a positive number.', 'Close', { duration: 3000 });
               return false;
          }
          if (!this.checkId.trim()) {
               this.snackBar.open('Check ID is required.', 'Close', { duration: 3000 });
               return false;
          }
          return true;
     }

     async cashTokenCheck(): Promise<void> {
          if (!this.validateInputs()) return;

          this.isLoading = true;
          this.errorMessage = '';
          this.txJson = null;

          try {
               const body = {
                    sender_seed: this.senderSeed.trim(),
                    token_name: this.tokenName.trim().toUpperCase(), // Ensure uppercase for currency code
                    token_issuer: this.tokenIssuer.trim(),
                    cash_amount: this.cashAmount.trim(),
                    check_id: this.checkId.trim(),
               };

               const headers = new HttpHeaders({
                    'Content-Type': 'application/json',
               });

               const response = await firstValueFrom(
                    this.http.post<CashTokenCheckApiResponse>('http://127.0.0.1:8000/xrpl/checks/cash/token', body, { headers })
               );

               console.log('Raw response:', response);

               if (response && response.status === 'success') {
                    this.txJson = response.result.tx_json;
                    this.snackBar.open(response.message, 'Close', { duration: 5000 });
               } else {
                    this.errorMessage = 'Failed to cash token check.';
                    this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
               }

               this.isLoading = false;
          } catch (error: any) {
               handleError(error, this.snackBar, 'Cashing XRP token check', {
                    setErrorMessage: (msg) => (this.errorMessage = msg),
                    setLoading: (loading) => (this.isLoading = loading),
               })
          }
     }

     // Format XRPL timestamp to local date string
     formatDate(xrplTimestamp: number): string {
          const unixTimestamp = xrplTimestamp + CalculationUtils.XRPL_EPOCH_OFFSET; // Adjust to Unix epoch
          const date = new Date(unixTimestamp * 1000); // Convert seconds to milliseconds
          return date.toLocaleString();
     }
}