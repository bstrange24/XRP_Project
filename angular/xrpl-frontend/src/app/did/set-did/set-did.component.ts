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
import { ValidationUtils } from '../../utlities/validation-utils';

// Define interfaces for the API response
interface TxJson {
  Account: string;
  DIDDocument: string;
  Data: string;
  Fee: string;
  Flags: number;
  LastLedgerSequence: number;
  Sequence: number;
  SigningPubKey: string;
  TransactionType: string;
  TxnSignature: string;
  URI: string;
  date: number;
  ledger_index: number;
}

interface DidSetApiResponse {
  status: string;
  message: string;
  result: {
    close_time_iso: string;
    ctid: string;
    hash: string;
    ledger_hash: string;
    ledger_index: number;
    meta: any; // You can expand this if needed
    tx_json: TxJson;
    validated: boolean;
  };
}

@Component({
  selector: 'app-set-did',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  templateUrl: './set-did.component.html',
  styleUrls: ['./set-did.component.css'],
})
export class SetDidComponent implements OnInit {
  accountSeed: string = '';
  document: string = '';
  uri: string = '';
  didData: string = '';
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

  async setDid(): Promise<void> {
    this.isLoading = true;
    this.errorMessage = '';
    this.hash = '';
    this.txJson = null;

    if (!ValidationUtils.areFieldsValid(this.accountSeed.trim(), this.document.trim(), this.uri.trim(), this.didData.trim())) {
      this.snackBar.open('Please fill in all required fields.', 'Close', {
        duration: 3000,
        panelClass: ['error-snackbar'],
      });
      this.isLoading = false;
      return;
    }

    try {
      const body = {
        account_seed: this.accountSeed.trim(),
        document: this.document.trim(),
        uri: this.uri.trim(),
        did_data: this.didData.trim(),
      };

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<DidSetApiResponse>('http://127.0.0.1:8000/xrpl/did/set', body, { headers })
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
        console.warn('No valid DID set data found in response:', response);
      }

      this.isLoading = false;
      this.hasSubmitted = true;
    } catch (error: any) {
      this.errorMessage = 'Error setting DID: ' + (error.message || 'Unknown error');
      this.snackBar.open(this.errorMessage, 'Close', {
        duration: 5000,
        panelClass: ['error-snackbar'],
      });
      this.isLoading = false;
      this.hasSubmitted = true;
    }
  }
}