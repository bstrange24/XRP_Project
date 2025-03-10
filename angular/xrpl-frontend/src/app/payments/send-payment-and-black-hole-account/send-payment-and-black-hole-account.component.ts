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

interface TxJson {
  Account: string;
  Destination: string;
  Amount: string; // In drops
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

interface SendPaymentAndBlackHoleAccountApiResponse {
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
  sender?: string; // Optional, may not be in response
  receiver?: string; // Optional, may not be in response
}

@Component({
  selector: 'app-send-payment-and-black-hole-account',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  templateUrl: './send-payment-and-black-hole-account.component.html',
  styleUrls: ['./send-payment-and-black-hole-account.component.css'],
})
export class SendPaymentAndBlackHoleAccountComponent implements OnInit {
  account: string = '';
  senderSeed: string = '';
  isLoading: boolean = false;
  errorMessage: string = '';
  txJson: TxJson | null = null;
  sender: string = '';
  receiver: string = '';

  // XRPL epoch offset (seconds from Unix epoch to XRPL epoch: Jan 1, 2000)
  private readonly XRPL_EPOCH_OFFSET = 946684800;

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient
  ) {}

  ngOnInit(): void {}

  // Validate inputs before submission
  private validateInputs(): boolean {
    if (!this.account.trim()) {
      this.snackBar.open('Receiver account is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.isValidXrpAddress(this.account.trim())) {
      this.snackBar.open('Receiver account must be a valid XRP address.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.senderSeed.trim()) {
      this.snackBar.open('Sender seed is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.isValidXrpSeed(this.senderSeed.trim())) {
      this.snackBar.open('Sender seed must be a valid XRP seed.', 'Close', { duration: 3000 });
      return false;
    }
    return true;
  }

  // Validate XRP address
  private isValidXrpAddress(address: string): boolean {
    try {
      return XRPL.isValidAddress(address);
    } catch (error) {
      console.error('Error validating XRP address:', error);
      return false;
    }
  }

  // Validate XRP seed (basic check)
  private isValidXrpSeed(seed: string): boolean {
    try {
      return seed.startsWith('sEd') && seed.length >= 29 && seed.length <= 35;
    } catch (error) {
      console.error('Error validating XRP seed:', error);
      return false;
    }
  }

  async sendPaymentAndBlackHoleAccount(): Promise<void> {
    if (!this.validateInputs()) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.txJson = null;
    this.sender = '';
    this.receiver = '';

    try {
      const body = {
        account: this.account.trim(),
        sender_seed: this.senderSeed.trim(),
      };

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<SendPaymentAndBlackHoleAccountApiResponse>(
          'http://127.0.0.1:8000/xrpl/payment/send-xrp/black-hole-account/',
          body,
          { headers }
        )
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success') {
        this.txJson = response.result.tx_json;
        this.sender = response.sender || this.txJson.Account; // Fallback to Account if sender not provided
        this.receiver = response.receiver || this.account; // Fallback to input account if receiver not provided
        this.snackBar.open(response.message, 'Close', { duration: 5000 });
      } else {
        this.errorMessage = 'Failed to send payment and black hole account.';
        this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      }

      this.isLoading = false;
    } catch (error: any) {
      this.errorMessage = 'Error sending payment and black holing account: ' + (error.message || 'Unknown error');
      this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      this.isLoading = false;
    }
  }

  // Format amount from drops to XRP with 2 decimal places
  formatAmount(drops: string): string {
    const amount = parseFloat(drops) / 1000000; // Convert drops to XRP
    return isNaN(amount) ? drops : amount.toFixed(2);
  }

  // Format XRPL timestamp to local date string
  formatDate(xrplTimestamp: number): string {
    const unixTimestamp = xrplTimestamp + this.XRPL_EPOCH_OFFSET; // Adjust to Unix epoch
    const date = new Date(unixTimestamp * 1000); // Convert seconds to milliseconds
    return date.toLocaleString();
  }
}