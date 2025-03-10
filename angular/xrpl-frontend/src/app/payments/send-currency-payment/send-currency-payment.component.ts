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

interface Amount {
  currency: string;
  issuer: string;
  value: string;
}

interface TxJson {
  Account: string;
  Destination: string;
  Amount: Amount; // Destination currency
  SendMax: Amount; // Source currency
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

interface SendCurrencyPaymentApiResponse {
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
  selector: 'app-send-currency-payment',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  templateUrl: './send-currency-payment.component.html',
  styleUrls: ['./send-currency-payment.component.css'],
})
export class SendCurrencyPaymentComponent implements OnInit {
  senderSeed: string = '';
  destinationAddress: string = '';
  sourceCurrency: string = '';
  sourceIssuer: string = '';
  destinationCurrency: string = '';
  destinationIssuer: string = '';
  amountToDeliver: string = '';
  maxToSpend: string = '';
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
    if (!this.senderSeed.trim()) {
      this.snackBar.open('Sender seed is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.isValidXrpSeed(this.senderSeed.trim())) {
      this.snackBar.open('Sender seed must be a valid XRP seed.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.destinationAddress.trim()) {
      this.snackBar.open('Destination address is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.isValidXrpAddress(this.destinationAddress.trim())) {
      this.snackBar.open('Destination address must be a valid XRP address.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.sourceCurrency.trim() || this.sourceCurrency.length !== 3) {
      this.snackBar.open('Source currency must be a 3-character code.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.sourceIssuer.trim()) {
      this.snackBar.open('Source issuer is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.isValidXrpAddress(this.sourceIssuer.trim())) {
      this.snackBar.open('Source issuer must be a valid XRP address.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.destinationCurrency.trim() || this.destinationCurrency.length !== 3) {
      this.snackBar.open('Destination currency must be a 3-character code.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.destinationIssuer.trim()) {
      this.snackBar.open('Destination issuer is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.isValidXrpAddress(this.destinationIssuer.trim())) {
      this.snackBar.open('Destination issuer must be a valid XRP address.', 'Close', { duration: 3000 });
      return false;
    }
    const amount = this.amountToDeliver.trim();
    if (!amount || isNaN(+amount) || +amount <= 0) {
      this.snackBar.open('Amount to deliver must be a positive number.', 'Close', { duration: 3000 });
      return false;
    }
    const max = this.maxToSpend.trim();
    if (!max || isNaN(+max) || +max <= 0) {
      this.snackBar.open('Max to spend must be a positive number.', 'Close', { duration: 3000 });
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

  async sendCurrencyPayment(): Promise<void> {
    if (!this.validateInputs()) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.txJson = null;
    this.sender = '';
    this.receiver = '';

    try {
      const body = {
        sender_seed: this.senderSeed.trim(),
        destination_address: this.destinationAddress.trim(),
        source_currency: this.sourceCurrency.trim().toUpperCase(),
        source_issuer: this.sourceIssuer.trim(),
        destination_currency: this.destinationCurrency.trim().toUpperCase(),
        destination_issuer: this.destinationIssuer.trim(),
        amount_to_deliver: this.amountToDeliver.trim(),
        max_to_spend: this.maxToSpend.trim(),
      };

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<SendCurrencyPaymentApiResponse>(
          'http://127.0.0.1:8000/xrpl/payment/send-cross-currency/',
          body,
          { headers }
        )
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success') {
        this.txJson = response.result.tx_json;
        this.sender = response.sender || this.txJson.Account; // Fallback to Account if sender not provided
        this.receiver = response.receiver || this.destinationAddress; // Fallback to input destination if receiver not provided
        this.snackBar.open(response.message, 'Close', { duration: 5000 });
      } else {
        this.errorMessage = 'Failed to send cross-currency payment.';
        this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      }

      this.isLoading = false;
    } catch (error: any) {
      this.errorMessage = 'Error sending cross-currency payment: ' + (error.message || 'Unknown error');
      this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      this.isLoading = false;
    }
  }

  // Format XRPL timestamp to local date string
  formatDate(xrplTimestamp: number): string {
    const unixTimestamp = xrplTimestamp + this.XRPL_EPOCH_OFFSET; // Adjust to Unix epoch
    const date = new Date(unixTimestamp * 1000); // Convert seconds to milliseconds
    return date.toLocaleString();
  }
}