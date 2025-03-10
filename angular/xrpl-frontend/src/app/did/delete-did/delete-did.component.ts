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

// Define interfaces for the API response
interface TxJson {
  Account: string;
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

interface DidDeleteApiResponse {
  status: string;
  message: string;
  result: {
    close_time_iso: string;
    ctid: string;
    hash: string;
    ledger_hash: string;
    ledger_index: number;
    meta: any; // Expand if needed
    tx_json: TxJson;
    validated: boolean;
  };
}

@Component({
  selector: 'app-delete-did',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  templateUrl: './delete-did.component.html',
  styleUrls: ['./delete-did.component.css'],
})
export class DeleteDidComponent implements OnInit {
  accountSeed: string = '';
  hash: string = '';
  txJson: TxJson | null = null;
  isLoading: boolean = false;
  errorMessage: string = '';
  hasSubmitted: boolean = false;

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient
  ) {}

  ngOnInit(): void {}

  private isFieldValid(): boolean {
    return !!this.accountSeed.trim();
  }

  async deleteDid(): Promise<void> {
    this.isLoading = true;
    this.errorMessage = '';
    this.hash = '';
    this.txJson = null;

    if (!this.isFieldValid()) {
      this.snackBar.open('Please enter a valid account seed.', 'Close', {
        duration: 3000,
        panelClass: ['error-snackbar'],
      });
      this.isLoading = false;
      return;
    }

    try {
      const body = {
        account_seed: this.accountSeed.trim(),
      };

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<DidDeleteApiResponse>('http://127.0.0.1:8000/xrpl/did/delete', body, { headers })
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success' && response.result) {
        this.hash = response.result.hash;
        this.txJson = response.result.tx_json;
        console.log('Hash:', this.hash);
        console.log('Tx JSON:', this.txJson);
      } else {
        this.hash = '';
        this.txJson = null;
        console.warn('No valid DID delete data found in response:', response);
      }

      this.isLoading = false;
      this.hasSubmitted = true;
    } catch (error: any) {
      this.errorMessage = 'Error deleting DID: ' + (error.message || 'Unknown error');
      this.snackBar.open(this.errorMessage, 'Close', {
        duration: 5000,
        panelClass: ['error-snackbar'],
      });
      this.isLoading = false;
      this.hasSubmitted = true;
    }
  }
}