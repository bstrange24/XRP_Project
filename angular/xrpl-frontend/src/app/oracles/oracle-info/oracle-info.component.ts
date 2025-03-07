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
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import * as XRPL from 'xrpl';
import { firstValueFrom } from 'rxjs';
import { WalletService } from '../../services/wallet-services/wallet.service';
import { CalculationUtils } from '../../utlities/calculation-utils';
import { handleError } from '../../utlities/error-handling-utils';

// Interfaces (adjusted for clarity)
interface PriceData {
     AssetPrice: string;
     BaseAsset: string;
     QuoteAsset: string;
     Scale: number;
}

interface PriceDataSeries {
     PriceData: PriceData;
     calculatedPrice?: number; // Added for transformed data
}

interface XamanWalletData {
     address: string;
     seed?: string;
}

@Component({
     selector: 'app-oracle-info',
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
          MatPaginatorModule,
     ],
     templateUrl: './oracle-info.component.html',
     styleUrl: './oracle-info.component.css',
})
export class OracleInfoComponent implements OnInit {
     account: string = '';
     trustLines: any[] = [];
     fullTrustLines: any[] = [];
     totalAccountLines: number = 0;
     currentPage: number = 1;
     pageSize: number = 10;
     isLoading: boolean = false;
     errorMessage: string = '';
     displayedColumns: string[] = ['AssetPrice', 'BaseAsset', 'QuoteAsset', 'Scale'];
     connectedWallet: XamanWalletData | null = null;
     hasFetched: boolean = false;

     constructor(
          private readonly snackBar: MatSnackBar,
          private readonly http: HttpClient,
          private readonly walletService: WalletService
     ) { }

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
          this.connectedWallet = this.walletService.getWallet();
          if (this.connectedWallet) {
               this.account = this.connectedWallet.address;
          } else {
               console.log('No wallet is connected. We need to get the user to input one.');
          }
     }

     async getPriceOracles(): Promise<void> {
          this.isLoading = true;
          this.errorMessage = '';
          this.fullTrustLines = [];
          this.trustLines = [];

          if (!this.account.trim() || !this.isValidXrpAddress(this.account)) {
               this.snackBar.open('Please enter a valid XRP account address.', 'Close', {
                    duration: 3000,
                    panelClass: ['error-snackbar'],
               });
               this.isLoading = false;
               return;
          }

          try {
               const body = {
                    oracle_creator_account: this.account.trim(),
                    page: this.currentPage.toString(),
                    page_size: this.pageSize.toString(),
               };

               const headers = new HttpHeaders({
                    'Content-Type': 'application/json',
               });

               const response = await firstValueFrom(
                    this.http.post<any>('http://127.0.0.1:8000/xrpl/oracle/price/get', body, { headers })
               );

               console.log('Raw response:', response);

               if (response && response.status === 'success' && Array.isArray(response.oracles) && response.oracles.length > 0) {
                    const oracleArray = response.oracles[0]; // This is an array: [{…}]
                    console.log('First oracle array:', oracleArray);
                    console.log('Keys in oracleArray:', Object.keys(oracleArray));

                    if (Array.isArray(oracleArray) && oracleArray.length > 0) {
                         // Aggregate all PriceDataSeries and calculate prices
                         this.fullTrustLines = oracleArray.reduce((acc: PriceDataSeries[], oracle: any) => {
                              if (Array.isArray(oracle.PriceDataSeries)) {
                                   const transformedSeries = oracle.PriceDataSeries.map((priceData: PriceDataSeries) => ({
                                        ...priceData,
                                        calculatedPrice: CalculationUtils.calculatePrice(priceData.PriceData.AssetPrice, priceData.PriceData.Scale)
                                   }));
                                   return acc.concat(transformedSeries);
                              }
                              return acc;
                         }, []);

                         this.totalAccountLines = this.fullTrustLines.length;
                         this.updateDisplayedTrustLines(); // Set initial page
                         console.log('Full trustLines:', this.fullTrustLines);
                    } else {
                         this.fullTrustLines = [];
                         this.trustLines = [];
                         this.totalAccountLines = 0;
                         console.warn('First oracle array is empty or not an array:', oracleArray);
                    }
               } else {
                    this.fullTrustLines = [];
                    this.trustLines = [];
                    this.totalAccountLines = 0;
                    console.warn('No valid oracles found in response:', response);
               }

               this.isLoading = false;
               this.hasFetched = true;
               console.log('Price data retrieved:', this.trustLines);
          } catch (error: any) {
               handleError(error, this.snackBar, 'Fetching Price Oracle data', {
                    setErrorMessage: (msg) => this.errorMessage = msg,
                    setLoading: (loading) => this.isLoading = loading,
                    setFetched: (fetched) => this.hasFetched = fetched
               });
          }
     }

     updateDisplayedTrustLines(): void {
          const start = (this.currentPage - 1) * this.pageSize;
          const end = start + this.pageSize;
          this.trustLines = this.fullTrustLines.slice(start, end);
     }

     onPageChange(event: PageEvent): void {
          this.currentPage = event.pageIndex + 1;
          this.pageSize = event.pageSize;
          this.updateDisplayedTrustLines();
     }
}