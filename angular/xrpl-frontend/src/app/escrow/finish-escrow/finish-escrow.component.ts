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
import { CalculationUtils } from '../../utlities/calculation-utils';

interface TxJson {
  Account: string;
  OfferSequence: number;
  Condition?: string; // Optional
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

interface FinishEscrowApiResponse {
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
  selector: 'app-finish-escrow',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  templateUrl: './finish-escrow.component.html',
  styleUrls: ['./finish-escrow.component.css'],
})
export class FinishEscrowComponent implements OnInit {
  escrowCreatorAccount: string = '';
  escrowCreatorSeed: string = '';
  offerSequence: string = ''; // Stored as string for input, validated as number
  condition: string = '';
  txnHash: string = '';
  isLoading: boolean = false;
  errorMessage: string = '';
  txJson: TxJson | null = null;

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient
  ) {}

  ngOnInit(): void {}

  // Validate inputs before submission
  private validateInputs(): boolean {
    if (!this.escrowCreatorAccount.trim()) {
      this.snackBar.open('Escrow creator account is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!ValidationUtils.isValidXrpAddress(this.escrowCreatorAccount.trim())) {
      this.snackBar.open('Escrow creator account must be a valid XRP address.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.escrowCreatorSeed.trim()) {
      this.snackBar.open('Escrow creator seed is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!ValidationUtils.isValidXrpSeed(this.escrowCreatorSeed.trim())) {
      this.snackBar.open('Escrow creator seed must be a valid XRP seed.', 'Close', { duration: 3000 });
      return false;
    }
    if (!ValidationUtils.isValidAmount(this.offerSequence.trim())) {
      this.snackBar.open('Offer sequence must be a non-negative number.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.txnHash.trim()) {
      this.snackBar.open('Transaction hash is required.', 'Close', { duration: 3000 });
      return false;
    }
    return true;
  }

  async finishEscrow(): Promise<void> {
    if (!this.validateInputs()) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.txJson = null;

    try {
      const body: any = {
        escrow_creator_account: this.escrowCreatorAccount.trim(),
        escrow_creator_seed: this.escrowCreatorSeed.trim(),
        offer_sequence: this.offerSequence.trim(),
        txn_hash: this.txnHash.trim(),
      };
      if (this.condition.trim()) {
        body.condition = this.condition.trim(); // Include only if provided
      }

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<FinishEscrowApiResponse>('http://127.0.0.1:8000/xrpl/escrow/finish/', body, { headers })
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success') {
        this.txJson = response.result.tx_json;
        this.snackBar.open(response.message, 'Close', { duration: 5000 });
      } else {
        this.errorMessage = 'Failed to finish escrow.';
        this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      }

      this.isLoading = false;
    } catch (error: any) {
      this.errorMessage = 'Error finishing escrow: ' + (error.message || 'Unknown error');
      this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      this.isLoading = false;
    }
  }

  // Format XRPL timestamp to local date string
  formatDate(xrplTimestamp: number): string {
    const unixTimestamp = xrplTimestamp + CalculationUtils.XRPL_EPOCH_OFFSET; // Adjust to Unix epoch
    const date = new Date(unixTimestamp * 1000); // Convert seconds to milliseconds
    return date.toLocaleString();
  }
}