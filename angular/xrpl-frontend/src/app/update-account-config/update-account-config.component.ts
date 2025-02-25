import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpParams } from '@angular/common/http';
import * as XRPL from 'xrpl';
import { firstValueFrom } from 'rxjs';

// Define interfaces for API responses
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
      AffectedNodes: any[]; // Simplified for brevity, expand if needed
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

// Define interface for ASF fields
interface AsfField {
  label: string;
  value: boolean | null;
  key: string; // To map back to the component properties
}

@Component({
  selector: 'app-update-account-config',
  standalone: true,
  imports: [CommonModule, FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatSelectModule],
  templateUrl: './update-account-config.component.html',
  styleUrls: ['./update-account-config.component.css']
})
export class UpdateAccountConfigComponent implements OnInit {
  account: string = ''; // XRP wallet address
  generatedSeed: string | null = null; // Store the fetched or generated seed
  asfFields: AsfField[] = []; // Array to hold ASF fields for grid layout
  responseMessage: string | null = null;
  isLoading: boolean = false;
  errorMessage: string = '';

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient
  ) {}

  // Validate XRP wallet address using xrpl
  private isValidXrpAddress(address: string): boolean {
    if (!address || typeof address !== 'string') return false;
    
    try {
      return XRPL.isValidAddress(address.trim());
    } catch (error) {
      console.error('Error validating XRP address:', error);
      return false;
    }
  }

  // // Fetch seed from backend for the given account
  // private async fetchSeedFromAccount(account: string): Promise<string> {
  //   try {
  //     const response = await firstValueFrom(this.http.get<GetAccountSeedResponse>(`http://127.0.0.1:8000/xrpl/get-account-seed/${account.trim()}/`));
  //     if (response.status !== 'success' || !response.seed) {
  //       throw new Error(response.message || 'Failed to fetch seed for the account.');
  //     }
  //     return response.seed; // Return the seed as a string
  //   } catch (error: any) {
  //     console.error('Error fetching seed from account:', error);
  //     throw new Error(`Failed to fetch seed from account: ${error.message}`);
  //   }
  // }

  // Fetch seed from backend for the given account
  private async fetchSeedFromAccount(account: string): Promise<string> {
    return 'sEd7dRirwCn2v8hJrGkRvrsKRpkriPT';
    // try {
    //   const response = await firstValueFrom(this.http.get<GetAccountSeedResponse>(`http://127.0.0.1:8000/xrpl/get-account-seed/${account.trim()}/`));
    //   if (response.status !== 'success' || !response.seed) {
    //     throw new Error(response.message || 'Failed to fetch seed for the account.');
    //   }
      // return response.seed; // Return the seed as a string
    // } catch (error: any) {
      // console.error('Error fetching seed from account:', error);
      // throw new Error(`Failed to fetch seed from account: ${error.message}`);
    // }
  }

  ngOnInit(): void {
    this.resetFields(); // Initialize fields as null
  }

  // Reset all fields to null or empty
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

  // Method to fetch initial values when triggered by the user
  async fetchInitialValues(): Promise<void> {
    if (!this.account.trim() || !this.isValidXrpAddress(this.account)) {
      this.snackBar.open('Please enter a valid XRP account address to load initial values.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';
    this.resetFields(); // Reset fields before loading new values

    try {
      // Fetch seed from the backend using the account
      this.generatedSeed = await this.fetchSeedFromAccount(this.account);
      console.log('Fetched seed:', this.generatedSeed);

      const response = await firstValueFrom(this.http.get<GetAccountConfigResponse>(`http://127.0.0.1:8000/xrpl/get-account-config/${this.account.trim()}/`));
      const flags = response.result.account_flags;

      // Update asfFields values based on the response
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
            field.value = false; // Not directly set, assuming false by default
            break;
          case 'asfAuthorizedNftokenMinter':
            field.value = false; // Not directly set, assuming false by default
            break;
        }
      });

      this.isLoading = false;
    } catch (error: any) {
      console.error('Error loading initial account config:', error);
      let errorMessage: string;
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error as any).message;
      } else {
        errorMessage = 'An unexpected error occurred while loading initial account config.';
      }
      this.errorMessage = errorMessage;
      this.snackBar.open(this.errorMessage, 'Close', {
        duration: 3000,
        panelClass: ['error-snackbar']
      });
      this.isLoading = false;
    }
  }

  async updateAccountConfig(): Promise<void> {
    this.isLoading = true;
    this.errorMessage = '';
    this.responseMessage = null;

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

    // Prepare params from asfFields
    const params = new HttpParams()
      .set('wallet_seed', this.generatedSeed) // Use the fetched seed
      .set('asf_account_txn_id', this.asfFields.find(f => f.key === 'asfAccountTxnId')?.value?.toString() || 'false')
      .set('asf_allow_trustline_clawback', this.asfFields.find(f => f.key === 'asfAllowTrustlineClawback')?.value?.toString() || 'false')
      .set('asf_authorized_nftoken_minter', this.asfFields.find(f => f.key === 'asfAuthorizedNftokenMinter')?.value?.toString() || 'false')
      .set('asf_default_ripple', this.asfFields.find(f => f.key === 'asfDefaultRipple')?.value?.toString() || 'false')
      .set('asf_deposit_auth', this.asfFields.find(f => f.key === 'asfDepositAuth')?.value?.toString() || 'false')
      .set('asf_disable_master', this.asfFields.find(f => f.key === 'asfDisableMaster')?.value?.toString() || 'false')
      .set('asf_disable_incoming_check', this.asfFields.find(f => f.key === 'asfDisableIncomingCheck')?.value?.toString() || 'false')
      .set('asf_disable_incoming_nftoken_offer', this.asfFields.find(f => f.key === 'asfDisableIncomingNftokenOffer')?.value?.toString() || 'false')
      .set('asf_disable_incoming_paychan', this.asfFields.find(f => f.key === 'asfDisableIncomingPaychan')?.value?.toString() || 'false')
      .set('asf_disable_incoming_trustline', this.asfFields.find(f => f.key === 'asfDisableIncomingTrustline')?.value?.toString() || 'false')
      .set('asf_disallow_XRP', this.asfFields.find(f => f.key === 'asfDisallowXRP')?.value?.toString() || 'false')
      .set('asf_global_freeze', this.asfFields.find(f => f.key === 'asfGlobalFreeze')?.value?.toString() || 'false')
      .set('asf_no_freeze', this.asfFields.find(f => f.key === 'asfNoFreeze')?.value?.toString() || 'false')
      .set('asf_require_auth', this.asfFields.find(f => f.key === 'asfRequireAuth')?.value?.toString() || 'false')
      .set('asf_require_dest', this.asfFields.find(f => f.key === 'asfRequireDest')?.value?.toString() || 'false');

    try {
      const response = await firstValueFrom(this.http.get<UpdateAccountConfigResponse>('http://127.0.0.1:8000/xrpl/update-account-config/', { params }));
      this.responseMessage = response.status === 'success' ? response.message : response.message;
      this.isLoading = false;
      console.log('Account config updated:', response);
    } catch (error: any) {
      console.error('Error updating account config:', error);
      let errorMessage: string;
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error as any).message;
      } else {
        errorMessage = 'An unexpected error occurred while updating account config.';
      }
      this.responseMessage = errorMessage;
      this.errorMessage = errorMessage;
      this.snackBar.open(this.errorMessage, 'Close', {
        duration: 3000,
        panelClass: ['error-snackbar']
      });
      this.isLoading = false;
    }
  }
}

  // Fetch seed from backend for the given account
  // private async fetchSeedFromAccount(account: string): Promise<string> {
    // return 'sEd7dRirwCn2v8hJrGkRvrsKRpkriPT';
    // try {
    //   const response = await firstValueFrom(this.http.get<GetAccountSeedResponse>(`http://127.0.0.1:8000/xrpl/get-account-seed/${account.trim()}/`));
    //   if (response.status !== 'success' || !response.seed) {
    //     throw new Error(response.message || 'Failed to fetch seed for the account.');
    //   }
      // return response.seed; // Return the seed as a string
    // } catch (error: any) {
      // console.error('Error fetching seed from account:', error);
      // throw new Error(`Failed to fetch seed from account: ${error.message}`);
    // }
  // }
