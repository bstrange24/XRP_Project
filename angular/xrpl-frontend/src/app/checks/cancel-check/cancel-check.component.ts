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
  CheckID: string;
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

interface CancelCheckApiResponse {
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
  selector: 'app-cancel-check',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  templateUrl: './cancel-check.component.html',
  styleUrls: ['./cancel-check.component.css'],
})
export class CancelCheckComponent implements OnInit {
  accountSeed: string = '';
  checkId: string = '';
  isLoading: boolean = false;
  errorMessage: string = '';
  txJson: TxJson | null = null;

  // XRPL epoch offset (seconds from Unix epoch to XRPL epoch: Jan 1, 2000)
  private readonly XRPL_EPOCH_OFFSET = 946684800;

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient
  ) {}

  ngOnInit(): void {}

  // Validate inputs before submission
  private validateInputs(): boolean {
    if (!this.accountSeed.trim()) {
      this.snackBar.open('Account seed is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.isValidXrpSeed(this.accountSeed.trim())) {
      this.snackBar.open('Account seed must be a valid XRP seed.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.checkId.trim()) {
      this.snackBar.open('Check ID is required.', 'Close', { duration: 3000 });
      return false;
    }
    return true;
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

  async cancelCheck(): Promise<void> {
    if (!this.validateInputs()) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.txJson = null;

    try {
      const body = {
        account_seed: this.accountSeed.trim(),
        check_id: this.checkId.trim(),
      };

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<CancelCheckApiResponse>('http://127.0.0.1:8000/xrpl/checks/cancel', body, { headers })
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success') {
        this.txJson = response.result.tx_json;
        this.snackBar.open(response.message, 'Close', { duration: 5000 });
      } else {
        this.errorMessage = 'Failed to cancel check.';
        this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      }

      this.isLoading = false;
    } catch (error: any) {
      this.errorMessage = 'Error cancelling check: ' + (error.message || 'Unknown error');
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