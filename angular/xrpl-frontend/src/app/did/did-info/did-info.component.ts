import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatTableModule } from '@angular/material/table';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatMenuModule } from '@angular/material/menu';
import { MatSelectModule } from '@angular/material/select';
import { MatOptionModule } from '@angular/material/core';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { RouterModule } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import * as XRPL from 'xrpl';
import { firstValueFrom } from 'rxjs';
import { WalletService } from '../../services/wallet-services/wallet.service';
import { handleError } from '../../utlities/error-handling-utils';
import { ValidationUtils } from '../../utlities/validation-utils';

// Define interfaces for the API response
interface DidNode {
     Account: string;
     DIDDocument: string;
     Data: string;
     Flags: number;
     LedgerEntryType: string;
     OwnerNode: string;
     PreviousTxnID: string;
     PreviousTxnLgrSeq: number;
     URI: string;
     index: string;
}

interface DidApiResponse {
     status: string;
     message: string;
     result: {
          index: string;
          ledger_hash: string;
          ledger_index: number;
          node: DidNode;
          validated: boolean;
     };
}

interface XamanWalletData {
     address: string;
     seed?: string;
}

@Component({
     selector: 'app-did-info',
     standalone: true,
     imports: [
          CommonModule,
          FormsModule,
          MatCardModule,
          MatFormFieldModule,
          MatInputModule,
          MatButtonModule,
          MatExpansionModule,
          MatTableModule,
          MatToolbarModule,
          MatMenuModule,
          MatSelectModule,
          MatOptionModule,
          MatIconModule,
          MatTabsModule,
          RouterModule,
     ],
     templateUrl: './did-info.component.html',
     styleUrls: ['./did-info.component.css'],
})
export class DidInfoComponent implements OnInit {
     account: string = '';
     didNode: DidNode | null = null;
     ledgerHash: string = '';
     ledgerIndex: number = 0;
     isLoading: boolean = false;
     errorMessage: string = '';
     connectedWallet: XamanWalletData | null = null;
     hasFetched: boolean = false;

     constructor(
          private readonly snackBar: MatSnackBar,
          private readonly http: HttpClient,
          private readonly walletService: WalletService
     ) { }

     // private isValidXrpAddress(address: string): boolean {
     //      if (!address || typeof address !== 'string') return false;
     //      try {
     //           return XRPL.isValidAddress(address.trim());
     //      } catch (error) {
     //           console.error('Error validating XRP address:', error);
     //           return false;
     //      }
     // }

     ngOnInit(): void {
          this.connectedWallet = this.walletService.getWallet();
          if (this.connectedWallet) {
               this.account = this.connectedWallet.address;
          } else {
               console.log('No wallet is connected. User needs to input an address.');
          }
     }

     async getDidInfo(): Promise<void> {
          this.isLoading = true;
          this.errorMessage = '';
          this.didNode = null;
          this.ledgerHash = '';
          this.ledgerIndex = 0;

          if (!this.account.trim() || !ValidationUtils.isValidXrpAddress(this.account)) {
               this.snackBar.open('Please enter a valid XRP account address.', 'Close', {
                    duration: 3000,
                    panelClass: ['error-snackbar'],
               });
               this.isLoading = false;
               return;
          }

          try {
               const body = {
                    account: this.account.trim(), // Adjust this key based on your API's expected parameter
               };

               const headers = new HttpHeaders({
                    'Content-Type': 'application/json',
               });

               const response = await firstValueFrom(
                    this.http.post<DidApiResponse>('http://127.0.0.1:8000/xrpl/did/get', body, { headers })
               );

               console.log('Raw response:', response);

               if (response && response.status === 'success' && response.result) {
                    this.didNode = response.result.node;
                    this.ledgerHash = response.result.ledger_hash;
                    this.ledgerIndex = response.result.ledger_index;
                    console.log('DID Node:', this.didNode);
                    console.log('Ledger Hash:', this.ledgerHash);
                    console.log('Ledger Hash:', this.ledgerIndex);
               } else {
                    this.didNode = null;
                    this.ledgerHash = '';
                    this.ledgerIndex = 0;
                    console.warn('No valid DID data found in response:', response);
               }

               this.isLoading = false;
               this.hasFetched = true;
          } catch (error: any) {
               handleError(error, this.snackBar, 'Fetching DID Information', {
                    setErrorMessage: (msg) => (this.errorMessage = msg),
                    setLoading: (loading) => (this.isLoading = loading),
                    setFetched: (fetched) => (this.hasFetched = fetched),
               });
          }
     }
}