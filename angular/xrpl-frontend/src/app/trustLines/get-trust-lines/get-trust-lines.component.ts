import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import * as XRPL from 'xrpl';
import { firstValueFrom } from 'rxjs';
import { WalletService } from '../../services/wallet-services/wallet.service';

// Define the interface for the API response
interface TrustLinesResponse {
     status: string;
     message: string;
     trust_lines: {
          account: string;
          balance: string;
          currency: string;
          limit: string;
          limit_peer: string;
          no_ripple: boolean;
          no_ripple_peer: boolean;
          quality_in: number;
          quality_out: number;
     }[];
     total_account_lines: number;
     pages: number;
     current_page: number;
}

interface XamanWalletData {
     address: string;
     seed?: string; // Optional, as Xaman doesn’t expose seeds
}

@Component({
     selector: 'app-get-trust-lines',
     standalone: true,
     imports: [
          CommonModule, 
          FormsModule, 
          MatCardModule, 
          MatFormFieldModule, 
          MatInputModule, 
          MatButtonModule, 
          MatTableModule, 
          MatPaginatorModule
     ],
     templateUrl: './get-trust-lines.component.html',
     styleUrls: ['./get-trust-lines.component.css']
})
export class GetTrustLinesComponent implements OnInit {
     account: string = '';
     trustLines: any[] = [];
     totalAccountLines: number = 0;
     currentPage: number = 1;
     pageSize: number = 10;
     isLoading: boolean = false;
     errorMessage: string = '';
     displayedColumns: string[] = ['account', 'balance', 'currency', 'limit', 'limit_peer', 'no_ripple', 'no_ripple_peer', 'quality_in', 'quality_out'];
     connectedWallet: XamanWalletData | null = null;
     hasFetched: boolean = false;

     constructor(
          private readonly snackBar: MatSnackBar,
          private readonly http: HttpClient,
          private readonly walletService: WalletService
     ) { }

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
          // Get the wallet from the service when the component initializes
          this.connectedWallet = this.walletService.getWallet();
          if (this.connectedWallet) {
               this.account = this.connectedWallet.address;
          } else {
               console.log('No wallet is connected. We need to get the user to input one.')
          }
     }

     async getTrustLines(): Promise<void> {
          this.isLoading = true;
          this.errorMessage = '';
          this.trustLines = [];

          if (!this.account.trim() || !this.isValidXrpAddress(this.account)) {
               this.snackBar.open('Please enter a valid XRP account address.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
               this.isLoading = false;
               return;
          }

          try {
               const bodyData = {
                    account: this.account.trim(),
                    page: this.currentPage.toString(),
                    page_size: this.pageSize.toString()

               };

               const headers = new HttpHeaders({
                    'Content-Type': 'application/json',
               });

               const response = await firstValueFrom(
                    this.http.post<TrustLinesResponse>(
                         'http://127.0.0.1:8000/xrpl/trustline/account/info/',
                         bodyData,
                         { headers }
                    )
               );

               this.trustLines = response.trust_lines || [];
               this.totalAccountLines = response.total_account_lines || 0;
               this.isLoading = false;
               this.hasFetched = true;
               console.log('Trust lines retrieved:', response);
          } catch (error: any) {
               console.error('Error retrieving trust lines:', error);
               let errorMessage: string;
               if (error instanceof Error) {
                    errorMessage = error.message;
               } else if (typeof error === 'object' && error !== null && 'message' in error) {
                    errorMessage = (error).message;
               } else {
                    errorMessage = 'An unexpected error occurred while retrieving trust lines.';
               }
               this.errorMessage = errorMessage;
               this.snackBar.open(this.errorMessage, 'Close', {
                    duration: 3000,
                    panelClass: ['error-snackbar']
               });
               this.hasFetched = true;
               this.isLoading = false;
          }
     }

     onPageChange(event: PageEvent): void {
          this.currentPage = event.pageIndex + 1;
          this.pageSize = event.pageSize;
          this.getTrustLines();
     }
}