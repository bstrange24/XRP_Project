import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import * as XRPL from 'xrpl';
import { firstValueFrom } from 'rxjs';

// Define interfaces for API responses (unchanged)
interface GetAccountConfigResponse {
     status: string;
     message: string;
     result: {
          account_data: {
               Account: string;
               AccountTxnID: string;
               Balance: string;
               Flags: number;
               LedgerEntryType: string;
               OwnerCount: number;
               PreviousTxnID: string;
               PreviousTxnLgrSeq: number;
               Sequence: number;
               index: string;
          };
          account_flags: {
               allowTrustLineClawback: boolean;
               defaultRipple: boolean;
               depositAuth: boolean;
               disableMasterKey: boolean;
               disallowIncomingCheck: boolean;
               disallowIncomingNFTokenOffer: boolean;
               disallowIncomingPayChan: boolean;
               disallowIncomingTrustline: boolean;
               disallowIncomingXRP: boolean;
               globalFreeze: boolean;
               noFreeze: boolean;
               passwordSpent: boolean;
               requireAuthorization: boolean;
               requireDestinationTag: boolean;
          };
          ledger_hash: string;
          ledger_index: number;
          validated: boolean;
     };
}

interface GetAccountSeedResponse {
     status: string;
     message: string;
     seed: string;
}

interface UpdateAccountConfigResponse {
     status: string;
     message: string;
     transaction_hash: string;
     account: string;
     result: {
          close_time_iso: string;
          ctid: string;
          hash: string;
          ledger_hash: string;
          ledger_index: number;
          meta: {
               AffectedNodes: any[];
               TransactionIndex: number;
               TransactionResult: string;
          };
          tx_json: {
               Account: string;
               ClearFlag: number;
               Fee: string;
               Flags: number;
               LastLedgerSequence: number;
               Sequence: number;
               SigningPubKey: string;
               TransactionType: string;
               TxnSignature: string;
               date: number;
               ledger_index: number;
          };
          validated: boolean;
     };
}

interface AsfField {
     label: string;
     value: boolean | null;
     key: string;
}

@Component({
     selector: 'app-update-account-config',
     standalone: true,
     imports: [
          CommonModule,
          FormsModule,
          MatCardModule,
          MatFormFieldModule,
          MatInputModule,
          MatButtonModule,
          MatCheckboxModule
     ],
     templateUrl: './update-account-config.component.html',
     styleUrls: ['./update-account-config.component.css']
})
export class UpdateAccountConfigComponent implements OnInit {
     account: string = '';
     generatedSeed: string | null = null;
     asfFields: AsfField[] = [];
     responseMessage: string | null = null;
     isLoading: boolean = false;
     errorMessage: string = '';

     constructor(
          private readonly snackBar: MatSnackBar,
          private readonly http: HttpClient
     ) {}

     private isValidXrpAddress(address: string): boolean {
          if (!address || typeof address !== 'string') return false;
          try {
               return XRPL.isValidAddress(address.trim());
          } catch (error) {
               console.error('Error validating XRP address:', error);
               return false;
          }
     }

     private async fetchSeedFromAccount(account: string): Promise<string> {
          return 'sEdSCJUHe5sa2TE5CmUQoJHeogDKxie'; // Mocked for now
     }

     ngOnInit(): void {
          this.resetFields();
     }

     private resetFields(): void {
          this.generatedSeed = null;
          this.asfFields = [
               { label: 'ASF Account Txn ID', value: null, key: 'asfAccountTxnId' },
               { label: 'ASF Allow Trustline Clawback', value: null, key: 'asfAllowTrustlineClawback' },
               { label: 'ASF Authorized NFT Token Minter', value: null, key: 'asfAuthorizedNftokenMinter' },
               { label: 'ASF Default Ripple', value: null, key: 'asfDefaultRipple' },
               { label: 'ASF Deposit Auth', value: null, key: 'asfDepositAuth' },
               { label: 'ASF Disable Master', value: null, key: 'asfDisableMaster' },
               { label: 'ASF Disable Incoming Check', value: null, key: 'asfDisableIncomingCheck' },
               { label: 'ASF Disable Incoming NFT Token Offer', value: null, key: 'asfDisableIncomingNftokenOffer' },
               { label: 'ASF Disable Incoming Paychan', value: null, key: 'asfDisableIncomingPaychan' },
               { label: 'ASF Disable Incoming Trustline', value: null, key: 'asfDisableIncomingTrustline' },
               { label: 'ASF Disallow XRP', value: null, key: 'asfDisallowXRP' },
               { label: 'ASF Global Freeze', value: null, key: 'asfGlobalFreeze' },
               { label: 'ASF No Freeze', value: null, key: 'asfNoFreeze' },
               { label: 'ASF Require Auth', value: null, key: 'asfRequireAuth' },
               { label: 'ASF Require Dest', value: null, key: 'asfRequireDest' },
          ];
     }

     async fetchInitialValues(): Promise<void> {
          if (!this.account.trim() || !this.isValidXrpAddress(this.account)) {
               this.snackBar.open('Please enter a valid XRP account address to load initial values.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               return;
          }

          this.isLoading = true;
          this.errorMessage = '';
          this.responseMessage = null; // Clear previous response
          this.resetFields();

          try {
               this.generatedSeed = await this.fetchSeedFromAccount(this.account);
               console.log('Fetched seed:', this.generatedSeed);
               console.log('I:M HERE 5-----------------------')
               const bodyData = {
                    account: this.account.trim(),
               };

               const headers = new HttpHeaders({
                    'Content-Type': 'application/json',
               });

               const response = await firstValueFrom(
                    this.http.post<GetAccountConfigResponse>(
                         'http://127.0.0.1:8000/xrpl/account/config/',
                         bodyData,
                         { headers }
                    )
               );

               if (response.status !== 'success') {
                    throw new Error(response.message || 'Failed to fetch account configuration.');
               }

               const flags = response.result.account_flags;

               this.asfFields.forEach(field => {
                    switch (field.key) {
                         case 'asfAllowTrustlineClawback':
                              field.value = flags.allowTrustLineClawback;
                              break;
                         case 'asfDefaultRipple':
                              field.value = flags.defaultRipple;
                              break;
                         case 'asfDepositAuth':
                              field.value = flags.depositAuth;
                              break;
                         case 'asfDisableMaster':
                              field.value = flags.disableMasterKey;
                              break;
                         case 'asfDisableIncomingCheck':
                              field.value = flags.disallowIncomingCheck;
                              break;
                         case 'asfDisableIncomingNftokenOffer':
                              field.value = flags.disallowIncomingNFTokenOffer;
                              break;
                         case 'asfDisableIncomingPaychan':
                              field.value = flags.disallowIncomingPayChan;
                              break;
                         case 'asfDisableIncomingTrustline':
                              field.value = flags.disallowIncomingTrustline;
                              break;
                         case 'asfDisallowXRP':
                              field.value = flags.disallowIncomingXRP;
                              break;
                         case 'asfGlobalFreeze':
                              field.value = flags.globalFreeze;
                              break;
                         case 'asfNoFreeze':
                              field.value = flags.noFreeze;
                              break;
                         case 'asfRequireAuth':
                              field.value = flags.requireAuthorization;
                              break;
                         case 'asfRequireDest':
                              field.value = flags.requireDestinationTag;
                              break;
                         case 'asfAccountTxnId':
                              field.value = false; // Default to false (not in flags)
                              break;
                         case 'asfAuthorizedNftokenMinter':
                              field.value = false; // Default to false (not in flags)
                              break;
                    }
               });

               this.isLoading = false;
               this.responseMessage = 'Initial values loaded successfully.';
          } catch (error: any) {
               console.error('Error loading initial account config:', error);
               this.errorMessage = error.message || 'An unexpected error occurred while loading initial account config.';
               this.snackBar.open(this.errorMessage, 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               this.isLoading = false;
          }
     }

     async updateAccountConfig(): Promise<void> {
          if (!this.account.trim() || !this.isValidXrpAddress(this.account)) {
               this.snackBar.open('Please enter a valid XRP account address.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               this.isLoading = false;
               return;
          }

          if (!this.generatedSeed) {
               this.snackBar.open('Please load initial values to fetch a seed before updating.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               this.isLoading = false;
               return;
          }

          this.isLoading = true;
          this.errorMessage = '';
          this.responseMessage = null;
          this.generatedSeed = await this.fetchSeedFromAccount(this.account);

          const bodyData = {
               wallet_seed: this.generatedSeed,
               asf_account_txn_id: ((this.asfFields.find(f => f.key === 'asfAccountTxnId')?.value ?? false).toString()),
               asf_allow_trustline_clawback: ((this.asfFields.find(f => f.key === 'asfAllowTrustlineClawback')?.value ?? false).toString()),
               asf_authorized_nftoken_minter: ((this.asfFields.find(f => f.key === 'asfAuthorizedNftokenMinter')?.value ?? false).toString()),
               asf_default_ripple: ((this.asfFields.find(f => f.key === 'asfDefaultRipple')?.value ?? false).toString()),
               asf_deposit_auth: ((this.asfFields.find(f => f.key === 'asfDepositAuth')?.value ?? false).toString()),
               asf_disable_master: ((this.asfFields.find(f => f.key === 'asfDisableMaster')?.value ?? false).toString()),
               asf_disable_incoming_check: ((this.asfFields.find(f => f.key === 'asfDisableIncomingCheck')?.value ?? false).toString()),
               asf_disable_incoming_nftoken_offer: ((this.asfFields.find(f => f.key === 'asfDisableIncomingNftokenOffer')?.value ?? false).toString()),
               asf_disable_incoming_paychan: ((this.asfFields.find(f => f.key === 'asfDisableIncomingPaychan')?.value ?? false).toString()),
               asf_disable_incoming_trustline: ((this.asfFields.find(f => f.key === 'asfDisableIncomingTrustline')?.value ?? false).toString()),
               asf_disallow_XRP: ((this.asfFields.find(f => f.key === 'asfDisallowXRP')?.value ?? false).toString()),
               asf_global_freeze: ((this.asfFields.find(f => f.key === 'asfGlobalFreeze')?.value ?? false).toString()),
               asf_no_freeze: ((this.asfFields.find(f => f.key === 'asfNoFreeze')?.value ?? false).toString()),
               asf_require_auth: ((this.asfFields.find(f => f.key === 'asfRequireAuth')?.value ?? false).toString()),
               asf_require_dest: ((this.asfFields.find(f => f.key === 'asfRequireDest')?.value ?? false).toString()),
          };
          console.log('Request body:', bodyData); // Debug request

          const headers = new HttpHeaders({
               'Content-Type': 'application/json',
          });

          try {
               console.log('I:M HERE 6-----------------------')
               const response = await firstValueFrom(
                    this.http.put<UpdateAccountConfigResponse>(
                         'http://127.0.0.1:8000/xrpl/account/config/update/',
                         bodyData,
                         { headers }
                    )
               );
               this.responseMessage = response.message;
               this.isLoading = false;
               console.log('Account config updated:', response);
          } catch (error: any) {
               console.error('Error updating account config:', error);
               this.errorMessage = error.message || 'An unexpected error occurred while updating account config.';
               this.responseMessage = this.errorMessage;
               this.snackBar.open(this.errorMessage, 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               this.isLoading = false;
          }
     }
}