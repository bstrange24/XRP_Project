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
import { MatCheckboxModule } from '@angular/material/checkbox';
import { ValidationUtils } from '../../utlities/validation-utils';
import { CalculationUtils } from '../../utlities/calculation-utils';

interface Memo {
     Memo: {
          MemoData: string;
          MemoType: string;
          MemoFormat: string;
     };
}

interface TxJson {
     Account: string;
     DeliverMax: string; // In drops
     Destination: string;
     Fee: string;
     Flags: number;
     LastLedgerSequence: number;
     Memos?: Memo[];
     Sequence: number;
     SigningPubKey: string;
     TransactionType: string;
     TxnSignature: string;
     date: number;
     ledger_index: number;
}

interface SendPaymentApiResponse {
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
     sender: string;
     receiver: string;
}

@Component({
     selector: 'app-send-payment',
     standalone: true,
     imports: [
          CommonModule,
          FormsModule,
          MatCardModule,
          MatFormFieldModule,
          MatInputModule,
          MatButtonModule,
          MatCheckboxModule,
     ],
     templateUrl: './send-payment.component.html',
     styleUrls: ['./send-payment.component.css'],
})
export class SendPaymentComponent implements OnInit {
     senderSeed: string = '';
     receiverAccount: string = '';
     amountXrp: string = '';
     memoData: string = '';
     memoType: string = '';
     memoFormat: string = '';
     includeMemo: boolean = false; // Checkbox state
     isLoading: boolean = false;
     errorMessage: string = '';
     txJson: TxJson | null = null;
     sender: string = '';
     receiver: string = '';

     constructor(
          private readonly snackBar: MatSnackBar,
          private readonly http: HttpClient
     ) { }

     ngOnInit(): void { }

     // Clear memo fields when checkbox is unchecked
     onMemoChange(): void {
          if (!this.includeMemo) {
               this.memoData = '';
               this.memoType = '';
               this.memoFormat = '';
          }
     }

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
          if (!this.receiverAccount.trim()) {
               this.snackBar.open('Receiver account is required.', 'Close', { duration: 3000 });
               return false;
          }
          if (!ValidationUtils.isValidXrpAddress(this.receiverAccount.trim())) {
               this.snackBar.open('Receiver account must be a valid XRP address.', 'Close', { duration: 3000 });
               return false;
          }
          if (!ValidationUtils.isValidAmount(this.amountXrp.trim())) {
               this.snackBar.open('Amount in XRP must be a positive number.', 'Close', { duration: 3000 });
               return false;
          }
          if (this.includeMemo) {
               if (this.memoType.trim() && !CalculationUtils.ALLOWED_CHARS.test(this.memoType.trim())) {
                    this.snackBar.open('Memo type contains invalid characters.', 'Close', { duration: 3000 });
                    return false;
               }
               if (this.memoFormat.trim() && !CalculationUtils.ALLOWED_CHARS.test(this.memoFormat.trim())) {
                    this.snackBar.open('Memo format contains invalid characters.', 'Close', { duration: 3000 });
                    return false;
               }
               const memoSize = this.calculateMemoSize();
               if (memoSize > CalculationUtils.MAX_MEMO_SIZE) {
                    this.snackBar.open('Memo size exceeds 1 KB limit.', 'Close', { duration: 3000 });
                    return false;
               }
          }
          return true;
     }

     // Calculate memo size in bytes (simplified estimation)
     private calculateMemoSize(): number {
          const memoDataBytes = new TextEncoder().encode(this.memoData.trim()).length;
          const memoTypeBytes = new TextEncoder().encode(this.memoType.trim()).length;
          const memoFormatBytes = new TextEncoder().encode(this.memoFormat.trim()).length;
          return memoDataBytes + memoTypeBytes + memoFormatBytes;
     }

     async sendPayment(): Promise<void> {
          if (!this.validateInputs()) return;

          this.isLoading = true;
          this.errorMessage = '';
          this.txJson = null;
          this.sender = '';
          this.receiver = '';

          try {
               const body: any = {
                    sender_seed: this.senderSeed.trim(),
                    receiver_account: this.receiverAccount.trim(),
                    amount_xrp: this.amountXrp.trim(),
               };
               if (this.includeMemo) {
                    if (this.memoData.trim()) body.memo_data = this.memoData.trim();
                    if (this.memoType.trim()) body.memo_type = this.memoType.trim();
                    if (this.memoFormat.trim()) body.memo_format = this.memoFormat.trim();
               }

               const headers = new HttpHeaders({
                    'Content-Type': 'application/json',
               });

               const response = await firstValueFrom(
                    this.http.post<SendPaymentApiResponse>('http://127.0.0.1:8000/xrpl/payment/send-xrp/', body, { headers })
               );

               console.log('Raw response:', response);

               if (response && response.status === 'success') {
                    this.txJson = response.result.tx_json;
                    this.sender = response.sender;
                    this.receiver = response.receiver;
                    this.snackBar.open(response.message, 'Close', { duration: 5000 });
               } else {
                    this.errorMessage = 'Failed to send payment.';
                    this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
               }

               this.isLoading = false;
          } catch (error: any) {
               this.errorMessage = 'Error sending payment: ' + (error.message || 'Unknown error');
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
          const unixTimestamp = xrplTimestamp + CalculationUtils.XRPL_EPOCH_OFFSET; // Adjust to Unix epoch
          const date = new Date(unixTimestamp * 1000); // Convert seconds to milliseconds
          return date.toLocaleString();
     }

     // Decode hex to readable string
     decodeHex(hex: string): string {
          try {
               const bytes = new Uint8Array(hex.match(/.{1,2}/g)!.map(byte => parseInt(byte, 16)));
               return new TextDecoder().decode(bytes);
          } catch (error) {
               console.error('Error decoding hex:', error);
               return hex; // Return raw hex if decoding fails
          }
     }
}