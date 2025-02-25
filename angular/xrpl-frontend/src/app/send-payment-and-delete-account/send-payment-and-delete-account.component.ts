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
  selector: 'app-send-payment-and-delete-account',
  standalone: true,
  imports: [CommonModule, FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  templateUrl: './send-payment-and-delete-account.component.html',
  styleUrls: ['./send-payment-and-delete-account.component.css']
})
export class SendPaymentAndDeleteAccountComponent {
  senderSeed: string = '';
  receivingAccount: string = '';
  actionResult: any | null = null;
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

  async sendPaymentAndDeleteAccount(): Promise<void> {
    // Show confirmation alert
    if (!confirm('Are you sure you want to send a payment and delete the account? This action cannot be undone.')) {
      return; // Cancel if user clicks "Cancel"
    }

    this.isLoading = true;
    this.errorMessage = '';
    this.actionResult = null;

    // Validate inputs
    if (!this.senderSeed.trim()) {
      this.snackBar.open('Please enter a sender wallet seed.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }
    if (!this.receivingAccount.trim() || !this.isValidXrpAddress(this.receivingAccount)) {
      this.snackBar.open('Please enter a valid receiving XRP address.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }

    try {
      const params = new HttpParams()
      .set('account', this.receivingAccount.trim())  
      .set('sender_seed', this.senderSeed.trim());
        

      const response = await firstValueFrom(this.http.get('http://127.0.0.1:8000/xrpl/send-xrp-payment-and-delete-account/', { params }));
      this.actionResult = response;
      this.isLoading = false;
      console.log('Payment sent and account deleted:', response);
    } catch (error: any) {
      console.error('Error sending payment and deleting account:', error);
      let errorMessage: string;
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (error.error.status === 'failure') {
        errorMessage = error.error.message
      }else if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error as any).message;
      } else {
        errorMessage = 'An unexpected error occurred while sending the payment and deleting the account.';
      }
      this.actionResult = { status: 'error', message: errorMessage };
      this.errorMessage = errorMessage;
      this.snackBar.open(this.errorMessage, 'Close', {
        duration: 3000,
        panelClass: ['error-snackbar']
      });
      this.isLoading = false;
    }
  }
}