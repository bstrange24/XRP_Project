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
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { WalletService } from '../../services/wallet-services/wallet.service';
import { ValidationUtils } from '../../utlities/validation-utils';
import { CalculationUtils } from '../../utlities/calculation-utils';
import { handleError } from '../../utlities/error-handling-utils';

interface XamanWalletData {
     address: string;
     seed?: string;
}

// Interfaces from your previous response
interface PriceData {
     AssetPrice: string;
     BaseAsset: string;
     QuoteAsset: string;
     Scale: number;
}

interface PriceDataSeries {
     PriceData: PriceData;
}

interface TxJson {
     Account: string;
     AssetClass?: string;
     Fee?: string;
     Flags?: number;
     LastLedgerSequence?: number;
     LastUpdateTime?: number;
     OracleDocumentID?: number;
     PriceDataSeries: PriceDataSeries[];
     Provider?: string;
     Sequence?: number;
     SigningPubKey?: string;
     TransactionType: string;
     TxnSignature?: string;
     URI?: string;
     date?: number;
     ledger_index?: number;
}

interface OracleResult {
     close_time_iso?: string;
     ctid?: string;
     hash: string;
     ledger_hash?: string;
     ledger_index: number;
     meta?: { AffectedNodes: any[]; TransactionIndex: number; TransactionResult: string };
     tx_json: TxJson;
     validated?: boolean;
}

@Component({
     selector: 'app-create-oracle',
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
     templateUrl: './create-oracle.component.html',
     styleUrl: './create-oracle.component.css'
})
export class CreateOracleComponent implements OnInit {
     account: string = '';
     trustLines: any[] = [];
     oracleResult: any = null; // New property to store the full result
     hash: string = ''; // To store the hash
     txJson: any = null; // To store tx_json
     totalAccountLines: number = 0;
     isLoading: boolean = false;
     errorMessage: string = '';
     displayedColumns: string[] = ['AssetPrice', 'BaseAsset', 'QuoteAsset', 'Scale'];
     connectedWallet: XamanWalletData | null = null;
     hasFetched: boolean = false;
     createOracleResult: OracleResult | null = null;
     senderSeed: string = '';
     documentId: string = '';
     provider: string = '';
     uri: string = '';
     assetClassType: string = '';
     baseAsset: string = '';
     quoteAsset: string = '';
     price: string = '';
     scale: string = '';

     constructor(
          private readonly snackBar: MatSnackBar,
          private readonly http: HttpClient,
          private readonly walletService: WalletService
     ) { }

     private isValidCommaSeparatedList(input: string): boolean {
          return ValidationUtils.isValidCommaSeparatedList(input);
     }

     private isValidNumberList(input: string): boolean {
          return ValidationUtils.isValidNumberList(input);
     }

     private isValidURI(uri: string): boolean {
          return ValidationUtils.isValidURI(uri);
     }

     ngOnInit(): void {
          this.connectedWallet = this.walletService.getWallet();
          if (this.connectedWallet) {
               this.account = this.connectedWallet.address;
          } else {
               console.log('No wallet is connected. We need to get the user to input one.');
          }
     }

     private showError(message: string): void {
          this.snackBar.open(message, 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
          this.isLoading = false;
     }

     private validateInputs(): boolean {
          const validations = [
               { condition: !this.senderSeed.trim(), message: 'Please enter a sender wallet seed.' },
               { condition: !this.documentId.trim(), message: 'Document ID cannot be blank.' },
               { condition: !this.provider.trim(), message: 'Provider cannot be blank.' },
               { condition: !this.uri.trim() || !this.isValidURI(this.uri), message: 'Please enter a valid URI.' },
               { condition: !this.assetClassType.trim(), message: 'Asset Class cannot be empty.' },
               { condition: !this.baseAsset.trim() || !this.isValidCommaSeparatedList(this.baseAsset), message: 'Invalid base asset. Must be a 3-character code.' },
               { condition: !this.quoteAsset.trim() || !this.isValidCommaSeparatedList(this.quoteAsset), message: 'Invalid quote asset. Must be a 3-character code.' },
               { condition: !this.price.trim() || !this.isValidNumberList(this.price), message: 'Invalid price. Must be a positive number.' },
               { condition: !this.scale.trim() || !this.isValidNumberList(this.scale), message: 'Invalid scale. Must be a positive number.' },
          ];

          for (const { condition, message } of validations) {
               if (condition) {
                    this.showError(message);
                    return false;
               }
          }
          return true;
     }

     async createPriceOracles(): Promise<void> {
          this.isLoading = true;
          this.errorMessage = '';
          this.trustLines = [];
          this.hash = '';
          this.txJson = null;

          if (!this.validateInputs()) return;

          console.log('this.baseAsset:' + this.baseAsset);
          console.log('this.quoteAsset: ' + this.quoteAsset);
          console.log('this.price: ' + this.price);
          console.log('this.scale: ' + this.scale);

          try {
               const body = {
                    account_seed: this.senderSeed.trim(),
                    oracle_document_id: this.documentId.trim(),
                    provider: this.provider.trim(),
                    uri: this.uri.trim(),
                    asset_class_type: this.assetClassType.trim(),
                    base_asset: this.baseAsset.split(',').map(baseAsset => baseAsset.trim()).filter(Boolean),
                    quote_asset: this.quoteAsset.split(',').map(quoteAsset => quoteAsset.trim()).filter(Boolean),
                    price: this.price.split(',').map(price => price.trim()).filter(Boolean),
                    scale_value: this.scale.split(',').map(scale => scale.trim()).filter(Boolean),
               };

               const headers = new HttpHeaders({
                    'Content-Type': 'application/json',
               });

               const response = await firstValueFrom(
                    this.http.post<any>('http://127.0.0.1:8000/xrpl/oracle/price/create', body, { headers })
               );

               console.log('Raw response:', response);

               if (response && response.status === 'success') {
                    this.oracleResult = response.result; // Store the full result
                    this.hash = this.oracleResult.hash; // Extract hash
                    this.txJson = this.oracleResult.tx_json; // Extract tx_json
                    this.trustLines = this.oracleResult.tx_json.PriceDataSeries.map((priceData: PriceDataSeries) => ({
                         ...priceData,
                         calculatedPrice: CalculationUtils.calculatePrice(priceData.PriceData.AssetPrice, priceData.PriceData.Scale)
                    }));
               } else {
                    this.trustLines = [];
                    this.totalAccountLines = 0;
                    console.warn('No valid oracles found in response:', response);
               }

               this.isLoading = false;
               this.hasFetched = true;
               console.log('Price data retrieved:', this.trustLines);
          } catch (error: any) {
               handleError(error, this.snackBar, 'Creating Price Oracle', {
                    setErrorMessage: (msg) => this.errorMessage = msg,
                    setLoading: (loading) => this.isLoading = loading,
                    setFetched: (fetched) => this.hasFetched = fetched
               });
          }
     }
}
