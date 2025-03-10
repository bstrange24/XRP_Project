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
import { MatCheckboxModule } from '@angular/material/checkbox';
import { ValidationUtils } from '../../utlities/validation-utils';
import { CalculationUtils } from '../../utlities/calculation-utils';
import { handleError } from '../../utlities/error-handling-utils';

interface TxJson {
     Account: string;
     Amount: string; // In drops
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

interface CreateEscrowApiResponse {
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
     selector: 'app-create-escrow',
     standalone: true,
     imports: [
          CommonModule,
          FormsModule,
          MatCardModule,
          MatFormFieldModule,
          MatInputModule,
          MatButtonModule,
          MatSelectModule,
          MatCheckboxModule,
     ],
     templateUrl: './create-escrow.component.html',
     styleUrls: ['./create-escrow.component.css'],
})
export class CreateEscrowComponent implements OnInit {
     escrowReceiverAccount: string = '';
     escrowCreatorSeed: string = '';
     amountToEscrow: string = '';
     finishAfterValue: number = 1;
     finishAfterUnit: string = 'min';
     cancelAfterValue: number = 2;
     cancelAfterUnit: string = 'min';
     timeBasedOnly: boolean = false;
     conditionalOnly: boolean = false;
     combination: boolean = true; // Default to match Postman example
     timeUnits: string[] = ['seconds', 'minutes', 'hours', 'days', 'months', 'years'];
     numberOptions: number[] = Array.from({ length: 100 }, (_, i) => i + 1);
     isLoading: boolean = false;
     errorMessage: string = '';
     txJson: TxJson | null = null;

     constructor(
          private readonly snackBar: MatSnackBar,
          private readonly http: HttpClient
     ) { }

     ngOnInit(): void { }

     // Validate inputs before submission
     private validateInputs(): boolean {
          if (!this.escrowReceiverAccount.trim()) {
               this.snackBar.open('Escrow receiver account is required.', 'Close', { duration: 3000 });
               return false;
          }
          if (!ValidationUtils.isValidXrpAddress(this.escrowReceiverAccount.trim())) {
               this.snackBar.open('Escrow receiver account must be a valid XRP address.', 'Close', { duration: 3000 });
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
          if (!ValidationUtils.isValidAmount(this.amountToEscrow.trim())) {
               this.snackBar.open('Amount to escrow must be a positive number.', 'Close', { duration: 3000 });
               return false;
          }
          if (!this.finishAfterValue || !this.finishAfterUnit) {
               this.snackBar.open('Finish after time must be specified.', 'Close', { duration: 3000 });
               return false;
          }
          if (!this.cancelAfterValue || !this.cancelAfterUnit) {
               this.snackBar.open('Cancel after time must be specified.', 'Close', { duration: 3000 });
               return false;
          }
          const checkboxCount = [this.timeBasedOnly, this.conditionalOnly, this.combination].filter(Boolean).length;
          if (checkboxCount !== 1) {
               this.snackBar.open('Exactly one of Time Based Only, Conditional Only, or Combination must be selected.', 'Close', { duration: 3000 });
               return false;
          }
          return true;
     }

     // Ensure mutual exclusivity of checkboxes
     onCheckboxChange(selected: 'timeBasedOnly' | 'conditionalOnly' | 'combination'): void {
          if (selected === 'timeBasedOnly') {
               this.timeBasedOnly = true;
               this.conditionalOnly = false;
               this.combination = false;
          } else if (selected === 'conditionalOnly') {
               this.timeBasedOnly = false;
               this.conditionalOnly = true;
               this.combination = false;
          } else if (selected === 'combination') {
               this.timeBasedOnly = false;
               this.conditionalOnly = false;
               this.combination = true;
          }
     }

     async createEscrow(): Promise<void> {
          if (!this.validateInputs()) return;

          this.isLoading = true;
          this.errorMessage = '';
          this.txJson = null;

          try {
               const body = {
                    escrow_receiver_account: this.escrowReceiverAccount.trim(),
                    escrow_creator_seed: this.escrowCreatorSeed.trim(),
                    amount_to_escrow: this.amountToEscrow.trim(),
                    finish_after_time: CalculationUtils.formatTime(this.finishAfterValue, this.finishAfterUnit),
                    cancel_after_time: CalculationUtils.formatTime(this.cancelAfterValue, this.cancelAfterUnit),
                    time_based_only: this.timeBasedOnly.toString(),
                    conditional_only: this.conditionalOnly.toString(),
                    combination: this.combination.toString(),
               };

               const headers = new HttpHeaders({
                    'Content-Type': 'application/json',
               });

               const response = await firstValueFrom(
                    this.http.post<CreateEscrowApiResponse>('http://127.0.0.1:8000/xrpl/escrow/create/', body, { headers })
               );

               console.log('Raw response:', response);

               if (response && response.status === 'success') {
                    this.txJson = response.result.tx_json;
                    this.snackBar.open(response.message, 'Close', { duration: 5000 });
               } else {
                    this.errorMessage = 'Failed to create escrow.';
                    this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
               }

               this.isLoading = false;
          } catch (error: any) {
               handleError(error, this.snackBar, 'Creating token check', {
                    setErrorMessage: (msg) => (this.errorMessage = msg),
                    setLoading: (loading) => (this.isLoading = loading),
               })
          }
     }

     // Format amount from drops to XRP with 2 decimal places
     formatAmount(amount: string): string {
          const drops = parseFloat(amount);
          const xrp = drops / 1000000; // Convert drops to XRP
          return isNaN(xrp) ? amount : xrp.toFixed(2);
     }

     // Format XRPL timestamp to local date string
     formatDate(xrplTimestamp: number): string {
          const unixTimestamp = xrplTimestamp + CalculationUtils.XRPL_EPOCH_OFFSET; // Adjust to Unix epoch
          const date = new Date(unixTimestamp * 1000); // Convert seconds to milliseconds
          return date.toLocaleString();
     }
}