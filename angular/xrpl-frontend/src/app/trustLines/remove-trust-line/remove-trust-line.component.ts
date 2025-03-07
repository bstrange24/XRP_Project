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

@Component({
     selector: 'app-remove-trust-line',
     standalone: true,
     imports: [CommonModule, FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule],
     templateUrl: './remove-trust-line.component.html',
     styleUrls: ['./remove-trust-line.component.css']
})
export class RemoveTrustLineComponent {
     senderSeed: string = '';
     issuerAddress: string = '';
     currencyCode: string = '';
     trustLineResult: any | null = null;
     isLoading: boolean = false;
     errorMessage: string = '';

     constructor(
          private readonly snackBar: MatSnackBar,
          private readonly http: HttpClient
     ) { }

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

     // Validate 3-character currency code (e.g., USD, CAD, EUR)
     private isValidCurrencyCode(code: string): boolean {
          if (!code || typeof code !== 'string') return false;
          const trimmedCode = code.trim().toUpperCase();
          return /^[A-Z]{3}$/.test(trimmedCode); // Matches exactly 3 uppercase letters
     }

     async removeTrustLine(): Promise<void> {
          this.isLoading = true;
          this.errorMessage = '';
          this.trustLineResult = null;

          // Validate inputs
          if (!this.senderSeed.trim()) {
               this.snackBar.open('Please enter a wallet seed.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               this.isLoading = false;
               return;
          }
          if (!this.issuerAddress.trim() || !this.isValidXrpAddress(this.issuerAddress)) {
               this.snackBar.open('Please enter a valid issuer XRP address.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               this.isLoading = false;
               return;
          }
          if (!this.currencyCode.trim() || !this.isValidCurrencyCode(this.currencyCode)) {
               this.snackBar.open('Please enter a valid 3-character currency code (e.g., USD, CAD).', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               this.isLoading = false;
               return;
          }

          try {
               const bodyData = {
                    sender_seed: this.senderSeed.trim(),
                    issuer_address: this.issuerAddress.trim(),
                    currency_code: this.currencyCode.trim()
               };

               const headers = new HttpHeaders({
                    'Content-Type': 'application/json',
               });

               const response = await firstValueFrom(this.http.post('http://127.0.0.1:8000/xrpl/trustline/remove/', bodyData, { headers }));
               this.trustLineResult = response;
               this.isLoading = false;
               console.log('Trust line removed:', response);
          } catch (error: any) {
               console.error('Error removing trust line:', error);
               let errorMessage: string;
               if (error instanceof Error) {
                    errorMessage = error.message;
               } else if (typeof error === 'object' && error !== null && 'message' in error) {
                    errorMessage = error.error.message
               } else {
                    errorMessage = 'An unexpected error occurred while removing the trust line.';
               }
               this.trustLineResult = { status: 'error', message: errorMessage };
               this.errorMessage = errorMessage;
               this.snackBar.open(this.errorMessage, 'Close', {
                    duration: 3000,
                    panelClass: ['error-snackbar']
               });
               this.isLoading = false;
          }
     }
}