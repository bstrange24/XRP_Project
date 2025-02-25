import { Component } from '@angular/core';
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

@Component({
  selector: 'app-send-currency-payment',
  standalone: true,
  imports: [CommonModule, FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  templateUrl: './send-currency-payment.component.html',
  styleUrls: ['./send-currency-payment.component.css']
})
export class SendCurrencyPaymentComponent {
  senderSeed: string = '';
  destinationAddress: string = '';
  sourceCurrency: string = '';
  sourceIssuer: string = '';
  destinationCurrency: string = '';
  destinationIssuer: string = '';
  amountToDeliver: string = '';
  maxToSpend: string = '';
  paymentResult: any | null = null;
  isLoading: boolean = false;
  errorMessage: string = '';

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient
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

  // Validate 3-character currency code (e.g., USD, EUR, CAD)
  private isValidCurrencyCode(code: string): boolean {
    if (!code || typeof code !== 'string') return false;
    const trimmedCode = code.trim().toUpperCase();
    return /^[A-Z]{3}$/.test(trimmedCode); // Matches exactly 3 uppercase letters
  }

  // Validate amount (positive number as string)
  private isValidAmount(amount: string): boolean {
    if (!amount || typeof amount !== 'string') return false;
    const trimmedAmount = amount.trim();
    const num = Number(trimmedAmount);
    return !isNaN(num) && num > 0;
  }

  async sendCurrencyPayment(): Promise<void> {
    this.isLoading = true;
    this.errorMessage = '';
    this.paymentResult = null;

    // Validate inputs
    try {
    if (!this.senderSeed.trim()) {
      this.snackBar.open('Please enter a sender wallet seed.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }
    if (!this.destinationAddress.trim() || !this.isValidXrpAddress(this.destinationAddress)) {
      this.snackBar.open('Please enter a valid destination XRP address.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }
    if (!this.sourceCurrency.trim() || !this.isValidCurrencyCode(this.sourceCurrency)) {
      this.snackBar.open('Please enter a valid 3-character source currency code (e.g., USD).', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }
    if (!this.sourceIssuer.trim() || !this.isValidXrpAddress(this.sourceIssuer)) {
      this.snackBar.open('Please enter a valid source issuer XRP address.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }
    if (!this.destinationCurrency.trim() || !this.isValidCurrencyCode(this.destinationCurrency)) {
      this.snackBar.open('Please enter a valid 3-character destination currency code (e.g., EUR).', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }
    if (!this.destinationIssuer.trim() || !this.isValidXrpAddress(this.destinationIssuer)) {
      this.snackBar.open('Please enter a valid destination issuer XRP address.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }
    if (!this.amountToDeliver.trim() || !this.isValidAmount(this.amountToDeliver)) {
      this.snackBar.open('Please enter a valid positive amount to deliver.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }
    if (!this.maxToSpend.trim() || !this.isValidAmount(this.maxToSpend)) {
      this.snackBar.open('Please enter a valid positive max to spend.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }
    } catch (error: any) {
      if (error instanceof Error) {
        this.errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null && 'message' in error) {
        this.errorMessage = (error as any).message;
      } else {
        this.errorMessage = 'An unexpected error occurred while sending the cross-currency payment.';
      }

      this.snackBar.open(this.errorMessage, 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }

    try {
      const params = new HttpParams()
        .set('sender_seed', this.senderSeed.trim())
        .set('destination_address', this.destinationAddress.trim())
        .set('source_currency', this.sourceCurrency.trim().toUpperCase())
        .set('source_issuer', this.sourceIssuer.trim())
        .set('destination_currency', this.destinationCurrency.trim().toUpperCase())
        .set('destination_issuer', this.destinationIssuer.trim())
        .set('amount_to_deliver', this.amountToDeliver.trim())
        .set('max_to_spend', this.maxToSpend.trim());

      const response = await firstValueFrom(this.http.get('http://127.0.0.1:8000/xrpl/send-cross-currency-payment/', { params }));
      this.paymentResult = response;
      this.isLoading = false;
      console.log('Cross-currency payment sent:', response);
    } catch (error: any) {
      console.error('Error sending cross-currency payment:', error);
      let errorMessage: string;
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error as any).message;
      } else {
        errorMessage = 'An unexpected error occurred while sending the cross-currency payment.';
      }
      this.paymentResult = { status: 'error', message: errorMessage };
      this.errorMessage = errorMessage;
      this.snackBar.open(this.errorMessage, 'Close', {
        duration: 3000,
        panelClass: ['error-snackbar']
      });
      this.isLoading = false;
    }
  }
}