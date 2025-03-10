import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatTableModule } from '@angular/material/table';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpParams } from '@angular/common/http';
import * as XRPL from 'xrpl';
import { firstValueFrom } from 'rxjs';

// Define the interface for the API response
interface CancelOffersResponse {
  status: string;
  message: string;
  result: {
    close_time_iso: string;
    ctid: string;
    hash: string;
    ledger_hash: string;
    ledger_index: number;
    meta: {
      AffectedNodes: {
        ModifiedNode?: {
          FinalFields: {
            Account: string;
            Balance: string;
            Flags: number;
            OwnerCount: number;
            Sequence: number;
          };
          LedgerEntryType: string;
          LedgerIndex: string;
          PreviousFields?: {
            Balance: string;
            OwnerCount: number;
            Sequence: number;
          };
          PreviousTxnID: string;
          PreviousTxnLgrSeq: number;
        };
        DeletedNode?: {
          FinalFields: {
            Account: string;
            BookDirectory: string;
            BookNode: string;
            Flags: number;
            OwnerNode: string;
            PreviousTxnID: string;
            PreviousTxnLgrSeq: number;
            Sequence: number;
            TakerGets: string;
            TakerPays: {
              currency: string;
              issuer: string;
              value: string;
            };
          };
          LedgerEntryType: string;
          LedgerIndex: string;
        };
      }[];
      TransactionIndex: number;
      TransactionResult: string;
    };
    tx_json: {
      Account: string;
      Fee: string;
      Flags: number;
      LastLedgerSequence: number;
      OfferSequence: number;
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

@Component({
  selector: 'app-cancel-account-offers',
  standalone: true,
  imports: [CommonModule, FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatTableModule],
  templateUrl: './cancel-account-offers.component.html',
  styleUrls: ['./cancel-account-offers.component.css']
})
export class CancelAccountOffersComponent implements OnInit {
  account: string = '';
  deletedNodes: any[] = []; // Store DeletedNode data
  txJson: any = null; // Store tx_json data
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

  ngOnInit(): void {
    // Optionally pre-load with a default or empty state
  }

  async cancelAccountOffers(): Promise<void> {
    this.isLoading = true;
    this.errorMessage = '';
    this.deletedNodes = [];
    this.txJson = null;

    if (!this.account.trim() || !this.isValidXrpAddress(this.account)) {
      this.snackBar.open('Please enter a valid XRP account address.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }

    try {
      const params = new HttpParams()
        .set('sender_seed', this.account.trim()); // Use sender_seed as per your API

      const response = await firstValueFrom(this.http.get<CancelOffersResponse>('http://127.0.0.1:8000/xrpl/cancel-account-offers/', { params }));
      
      // Extract only DeletedNode and tx_json from the response
      this.deletedNodes = response.result.meta.AffectedNodes
        .filter(node => node.DeletedNode)
        .map(node => node.DeletedNode);
      this.txJson = response.result.tx_json;
      
      this.isLoading = false;
      console.log('Offers cancelled:', response);
    } catch (error: any) {
      console.error('Error cancelling account offers:', error);
      let errorMessage: string;
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error as any).message;
      } else {
        errorMessage = 'An unexpected error occurred while cancelling account offers.';
      }
      this.errorMessage = errorMessage;
      this.snackBar.open(this.errorMessage, 'Close', {
        duration: 3000,
        panelClass: ['error-snackbar']
      });
      this.isLoading = false;
    }
  }
}