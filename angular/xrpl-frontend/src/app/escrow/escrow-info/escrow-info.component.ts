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
import { MatTableModule } from '@angular/material/table';
import * as XRPL from 'xrpl';
import { ValidationUtils } from '../../utlities/validation-utils';

interface EscrowEntry {
  escrow_id: string;
  sender: string;
  receiver: string;
  amount: string;
  prex_txn_id: string;
  redeem_date: string;
  expiry_date: string;
  condition: string;
}

interface TxJson {
  Account: string;
  Amount: string;
  CancelAfter: number;
  Condition: string;
  Destination: string;
  Fee: string;
  FinishAfter: number;
  Flags: number;
  LastLedgerSequence: number;
  Sequence: number;
  SigningPubKey: string;
  TransactionType: string;
  TxnSignature: string;
  date: number;
  ledger_index: number;
}

interface EscrowInfoApiResponse {
  status: string;
  message: string;
  result: {
    sent?: EscrowEntry[];
    received?: EscrowEntry[];
    close_time_iso?: string;
    ctid?: string;
    hash?: string;
    ledger_hash?: string;
    ledger_index?: number;
    meta?: any;
    tx_json?: TxJson;
    validated?: boolean;
  };
}

@Component({
  selector: 'app-escrow-info',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatTableModule,
  ],
  templateUrl: './escrow-info.component.html',
  styleUrls: ['./escrow-info.component.css'],
})
export class EscrowInfoComponent implements OnInit {
  escrowAccount: string = '';
  txHash: string = '';
  isLoading: boolean = false;
  errorMessage: string = '';
  sentData: EscrowEntry[] = [];
  receivedData: EscrowEntry[] = [];
  txJson: TxJson | null = null;
  sentColumns: string[] = ['escrow_id', 'sender', 'receiver', 'amount', 'prex_txn_id', 'redeem_date', 'expiry_date', 'condition'];
  receivedColumns: string[] = ['escrow_id', 'sender', 'receiver', 'amount', 'prex_txn_id', 'redeem_date', 'expiry_date', 'condition'];

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient
  ) {}

  ngOnInit(): void {}

  // Validate inputs before submission
  private validateInputs(): boolean {
    if (!this.escrowAccount.trim() && !this.txHash.trim()) {
      this.snackBar.open('Please provide either an escrow account or a transaction hash.', 'Close', { duration: 3000 });
      return false;
    }
    if (this.escrowAccount.trim() && !ValidationUtils.isValidXrpAddress(this.escrowAccount.trim())) {
      this.snackBar.open('Escrow account must be a valid XRP address.', 'Close', { duration: 3000 });
      return false;
    }
    return true;
  }

  // Validate XRP address using xrpl library
  // private isValidXrpAddress(address: string): boolean {
  //   try {
  //     return XRPL.isValidAddress(address);
  //   } catch (error) {
  //     console.error('Error validating XRP address:', error);
  //     return false;
  //   }
  // }

  async getEscrowInfo(): Promise<void> {
    if (!this.validateInputs()) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.sentData = [];
    this.receivedData = [];
    this.txJson = null;

    try {
      const body = {
        escrow_account: this.escrowAccount.trim() || '',
        tx_hash: this.txHash.trim() || '',
      };

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<EscrowInfoApiResponse>('http://127.0.0.1:8000/xrpl/escrow/account/info/', body, { headers })
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success') {
        if (response.result.sent || response.result.received) {
          // Handle escrow_account response
          this.sentData = response.result.sent || [];
          this.receivedData = response.result.received || [];
        } else if (response.result.tx_json) {
          // Handle tx_hash response
          this.txJson = response.result.tx_json;
        }
        this.snackBar.open(response.message, 'Close', { duration: 5000 });
      } else {
        this.errorMessage = 'Failed to retrieve escrow information.';
        this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      }

      this.isLoading = false;
    } catch (error: any) {
      this.errorMessage = 'Error retrieving escrow info: ' + (error.message || 'Unknown error');
      this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      this.isLoading = false;
    }
  }

  // Format amount to 5 decimal places
  formatAmount(amount: string): string {
    const num = parseFloat(amount);
    return isNaN(num) ? amount : num.toFixed(5);
  }

  // Format date string or timestamp
  formatDate(dateStr: string | number): string {
    const date = typeof dateStr === 'string' ? new Date(dateStr) : new Date(dateStr * 1000); // Handle timestamp if needed
    return isNaN(date.getTime()) ? String(dateStr) : date.toLocaleString();
  }
}