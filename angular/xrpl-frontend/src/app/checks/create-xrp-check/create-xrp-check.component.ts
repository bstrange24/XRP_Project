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
import { MatSelectModule } from '@angular/material/select';
import * as XRPL from 'xrpl';
import { ValidationUtils } from '../../utlities/validation-utils';
import { CalculationUtils } from '../../utlities/calculation-utils';

interface TxJson {
  Account: string;
  Destination: string;
  Expiration: number;
  Fee: string;
  Flags: number;
  LastLedgerSequence: number;
  SendMax: string; // In drops for XRP checks
  Sequence: number;
  SigningPubKey: string;
  TransactionType: string;
  TxnSignature: string;
  date: number;
  ledger_index: number;
}

interface CreateXrpCheckApiResponse {
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
  selector: 'app-create-xrp-check',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatSelectModule,
  ],
  templateUrl: './create-xrp-check.component.html',
  styleUrls: ['./create-xrp-check.component.css'],
})
export class CreateXrpCheckComponent implements OnInit {
  senderSeed: string = '';
  checkReceiverAddress: string = '';
  amountToDeliver: string = '';
  expirationValue: number = 1;
  expirationUnit: string = 'days';
  timeUnits: string[] = ['seconds', 'minutes', 'hours', 'days', 'month', 'years'];
  numberOptions: number[] = Array.from({ length: 100 }, (_, i) => i + 1);
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
    if (!this.senderSeed.trim()) {
      this.snackBar.open('Sender seed is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!ValidationUtils.isValidXrpSeed(this.senderSeed.trim())) {
      this.snackBar.open('Sender seed must be a valid XRP seed.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.checkReceiverAddress.trim()) {
      this.snackBar.open('Check receiver address is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!ValidationUtils.isValidXrpAddress(this.checkReceiverAddress.trim())) {
      this.snackBar.open('Check receiver address must be a valid XRP address.', 'Close', { duration: 3000 });
      return false;
    }
    if (!ValidationUtils.isValidAmount(this.amountToDeliver.trim())) {
      this.snackBar.open('Amount to deliver must be a positive number.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.expirationValue || !this.expirationUnit) {
      this.snackBar.open('Expiration must be specified.', 'Close', { duration: 3000 });
      return false;
    }
    return true;
  }

  // Validate XRP address
  // private isValidXrpAddress(address: string): boolean {
  //   try {
  //     return XRPL.isValidAddress(address);
  //   } catch (error) {
  //     console.error('Error validating XRP address:', error);
  //     return false;
  //   }
  // }

  // Validate XRP seed (basic check)
  // private isValidXrpSeed(seed: string): boolean {
  //   try {
  //     return seed.startsWith('sEd') && seed.length >= 29 && seed.length <= 35;
  //   } catch (error) {
  //     console.error('Error validating XRP seed:', error);
  //     return false;
  //   }
  // }

  // Format expiration for API (e.g., "1:days")
  // private formatExpiration(value: number, unit: string): string {
  //   return `${value}:${unit}`;
  // }

  async createXrpCheck(): Promise<void> {
    if (!this.validateInputs()) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.txJson = null;

    try {
      const body = {
        sender_seed: this.senderSeed.trim(),
        check_receiver_address: this.checkReceiverAddress.trim(),
        amount_to_deliver: this.amountToDeliver.trim(),
        expiration: CalculationUtils.formatTime(this.expirationValue, this.expirationUnit),
      };

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<CreateXrpCheckApiResponse>('http://127.0.0.1:8000/xrpl/checks/create/xrp', body, { headers })
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success') {
        this.txJson = response.result.tx_json;
        this.snackBar.open(response.message, 'Close', { duration: 5000 });
      } else {
        this.errorMessage = 'Failed to create XRP check.';
        this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      }

      this.isLoading = false;
    } catch (error: any) {
      this.errorMessage = 'Error creating XRP check: ' + (error.message || 'Unknown error');
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

  // Format SendMax from drops to XRP with 2 decimal places
  formatSendMax(sendMax: string): string {
    const drops = parseFloat(sendMax);
    const xrp = drops / 1000000; // Convert drops to XRP
    return isNaN(xrp) ? sendMax : xrp.toFixed(2);
  }
}