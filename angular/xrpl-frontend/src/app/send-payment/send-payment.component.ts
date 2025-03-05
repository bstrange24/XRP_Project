import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpParams, HttpHeaders } from '@angular/common/http';
import * as XRPL from 'xrpl';
import { firstValueFrom } from 'rxjs';

@Component({
  selector: 'app-send-payment',
  standalone: true,
  imports: [CommonModule, FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  templateUrl: './send-payment.component.html',
  styleUrls: ['./send-payment.component.css']
})
export class SendPaymentComponent {
  senderSeed: string = '';
  receiverAccount: string = '';
  amountXrp: string = ''; // Explicitly typed as string
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

  // Validate amount (positive number as string)
  private isValidAmount(amount: any): boolean {
    let amountStr: string;
    if (typeof amount === 'number') {
      amountStr = amount.toString(); // Convert number to string
      console.log('Converted amount to string:', amountStr);
    } else if (typeof amount === 'string') {
      amountStr = amount;
    } else {
      return false;
    }
    const trimmedAmount = amountStr.trim();
    const num = Number(trimmedAmount);
    return !isNaN(num) && num > 0;
  }

  async sendPayment(): Promise<void> {
    this.isLoading = true;
    this.errorMessage = '';
    this.paymentResult = null;

    console.log('senderSeed:', this.senderSeed, typeof this.senderSeed);
    console.log('receiverAccount:', this.receiverAccount, typeof this.receiverAccount);
    console.log('amountXrp before validation:', this.amountXrp, typeof this.amountXrp)

    try {
      // Validate inputs, ensuring amountXrp is treated as a string
      if (!this.senderSeed.trim()) {
        this.snackBar.open('Please enter a sender wallet seed.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
        this.isLoading = false;
        return;
      }
      if (!this.receiverAccount.trim() || !this.isValidXrpAddress(this.receiverAccount)) {
        this.snackBar.open('Please enter a valid receiver XRP address.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
        this.isLoading = false;
        return;
      }
      if (!this.amountXrp || !this.isValidAmount(this.amountXrp)) {
        this.snackBar.open('Please enter a valid positive XRP amount.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
        this.isLoading = false;
        return;
      }
    } catch (error: any) {
        this.snackBar.open('Please enter a sender wallet seed.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
        this.isLoading = false;
        return;
    }

    console.log('senderSeed:', this.senderSeed, typeof this.senderSeed);
    console.log('receiverAccount:', this.receiverAccount, typeof this.receiverAccount);
    console.log('amountXrp before before:', this.amountXrp, typeof this.amountXrp)
    this.amountXrp = this.amountXrp.toString()
    console.log('amountXrp before after conversion:', this.amountXrp, typeof this.amountXrp)

    try {
      const bodyData = {
        sender_seed: this.senderSeed.trim(), 
        receiver_account: this.receiverAccount.trim(),
        amount_xrp: this.amountXrp.trim()
      };
      
      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });
      
      const response = await firstValueFrom(
        this.http.post(
          'http://127.0.0.1:8000/xrpl/payment/send-xrp/',
          bodyData,
          { headers }
        )
      );

      this.paymentResult = response;
      this.isLoading = false;
      console.log('Payment sent:', response);
    } catch (error: any) {
      console.error('Error sending payment:', error);
      let errorMessage: string;
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error as any).message;
      } else {
        errorMessage = 'An unexpected error occurred while sending the payment.';
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