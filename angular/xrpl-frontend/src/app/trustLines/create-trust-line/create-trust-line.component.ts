import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import * as XRPL from 'xrpl';
import { firstValueFrom } from 'rxjs';
import { ValidationUtils } from '../../utlities/validation-utils';
import { handleError } from '../../utlities/error-handling-utils';

@Component({
     selector: 'app-create-trust-line',
     standalone: true,
     imports: [CommonModule, FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule],
     templateUrl: './create-trust-line.component.html',
     styleUrls: ['./create-trust-line.component.css']
})
export class CreateTrustLineComponent {
     senderSeed: string = '';
     issuerAddress: string = '';
     currencyCode: string = '';
     limit: number = 0;
     trustLineResult: any | null = null;
     isLoading: boolean = false;
     errorMessage: string = '';

     constructor(
          private readonly snackBar: MatSnackBar,
          private readonly http: HttpClient
     ) { }

     async createTrustLine(): Promise<void> {
          this.isLoading = true;
          this.errorMessage = '';
          this.trustLineResult = null;

          // Validate inputs
          if (!this.senderSeed.trim()) {
               this.snackBar.open('Please enter a wallet seed.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               this.isLoading = false;
               return;
          }
          if (!this.issuerAddress.trim() || !ValidationUtils.isValidXrpAddress(this.issuerAddress)) {
               this.snackBar.open('Please enter a valid issuer XRP address.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               this.isLoading = false;
               return;
          }
          if (!this.currencyCode.trim() || !ValidationUtils.isValidCurrencyCode(this.currencyCode)) {
               this.snackBar.open('Please enter a valid 3-character currency code (e.g., CAD, USD).', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               this.isLoading = false;
               return;
          }
          if (!this.limit || !ValidationUtils.isValidLimit(this.limit)) {
               this.snackBar.open('Please enter a valid positive limit.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               this.isLoading = false;
               return;
          }

          try {
               const bodyData = {
                    sender_seed: this.senderSeed.trim(),
                    issuer_address: this.issuerAddress.trim(),
                    currency_code: this.currencyCode.trim(),
                    limit: this.limit
               };

               const headers = new HttpHeaders({
                    'Content-Type': 'application/json',
               });

               const response = await firstValueFrom(this.http.post('http://127.0.0.1:8000/xrpl/trustline/set/', bodyData, { headers }));
               this.trustLineResult = response;
               this.isLoading = false;
               console.log('Trust line created:', response);
          } catch (error: any) {
                handleError(error, this.snackBar, 'Fetching DID Information', {
                                   setErrorMessage: (msg) => (this.errorMessage = msg),
                                   setLoading: (loading) => (this.isLoading = loading),
                              });
               // console.error('Error creating trust line:', error);
               // let errorMessage: string;
               // if (error instanceof Error) {
               //      errorMessage = error.message;
               // } else if (typeof error === 'object' && error !== null && 'message' in error) {
               //      errorMessage = error.error.message
               // } else {
               //      errorMessage = 'An unexpected error occurred while creating the trust line.';
               // }
               // this.trustLineResult = { status: 'error', message: errorMessage };
               // this.errorMessage = errorMessage;
               // this.snackBar.open(this.errorMessage, 'Close', {
               //      duration: 3000,
               //      panelClass: ['error-snackbar']
               // });
               // this.isLoading = false;
          }
     }
}