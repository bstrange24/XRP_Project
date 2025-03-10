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
import { CalculationUtils } from '../../utlities/calculation-utils';
import { handleError } from '../../utlities/error-handling-utils';

interface XamanWalletData {
     address: string;
     seed?: string;
}

// Interface for the PriceData object within PriceDataSeries
interface PriceData {
     AssetPrice: string; // Hexadecimal string
     BaseAsset: string;
     QuoteAsset: string;
     Scale: number;
}

// Interface for each PriceDataSeries entry
interface PriceDataSeries {
     PriceData: PriceData;
}

// Interface for tx_json
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
     TransactionType: string; // e.g., "OracleSet"
     TxnSignature?: string;
     URI?: string;
     date?: number;
     ledger_index?: number;
}

// Interface for the full result object
interface OracleResult {
     close_time_iso?: string;
     ctid?: string;
     hash: string;
     ledger_hash?: string;
     ledger_index: number;
     meta?: {
          // Define this further if needed
          AffectedNodes: any[]; 
          TransactionIndex: number;
          TransactionResult: string;
     };
     tx_json: TxJson;
     validated?: boolean;
}

@Component({
     selector: 'app-delete-oracle',
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
     templateUrl: './delete-oracle.component.html',
     styleUrl: './delete-oracle.component.css'
})
export class DeleteOracleComponent implements OnInit {
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
          ];

          for (const { condition, message } of validations) {
               if (condition) {
                    this.showError(message);
                    return false;
               }
          }
          return true;
     }

     async deletePriceOracles(): Promise<void> {
          this.isLoading = true;
          this.errorMessage = '';
          this.trustLines = [];
          this.hash = '';
          this.txJson = null;

          if (!this.validateInputs()) return;

          try {
               const body = {
                    account_seed: this.senderSeed.trim(),
                    oracle_document_id: this.documentId.trim(),
               };

               const headers = new HttpHeaders({
                    'Content-Type': 'application/json',
               });

               const response = await firstValueFrom(
                    this.http.post<any>('http://127.0.0.1:8000/xrpl/oracle/price/delete', body, { headers })
               );

               console.log('Raw response:', response);

               if (response && response.status === 'success') {
                    // Store the full result
                    this.oracleResult = response.result;
                    // Extract hash
                    this.hash = this.oracleResult.hash;
                    // Extract tx_json (optional)
                    this.txJson = this.oracleResult.tx_json;

                    // Extract PriceDataSeries from the DeletedNode in meta.AffectedNodes
                    const affectedNodes = this.oracleResult.meta.AffectedNodes;
                    const deletedNode = affectedNodes.find((node: any) => node.DeletedNode && node.DeletedNode.LedgerEntryType === 'Oracle');
                    if (deletedNode?.DeletedNode?.FinalFields && Array.isArray(deletedNode.DeletedNode.FinalFields.PriceDataSeries)) {
                         this.trustLines = deletedNode.DeletedNode.FinalFields.PriceDataSeries.map((priceData: any) => ({
                              ...priceData,
                              calculatedPrice: CalculationUtils.calculatePrice(priceData.PriceData.AssetPrice, priceData.PriceData.Scale)
                         }));
                         this.totalAccountLines = this.trustLines.length;
                    } else {
                         this.trustLines = [];
                         this.totalAccountLines = 0;
                         console.warn('No deleted PriceDataSeries found in response:', response);
                    }
               } else {
                    this.trustLines = [];
                    this.totalAccountLines = 0;
                    console.warn('No valid result found in response:', response);
               }

               this.isLoading = false;
               this.hasFetched = true;
               console.log('Price data retrieved:', this.trustLines);
          } catch (error: any) {
               handleError(error, this.snackBar, 'deleting price oracle', {
                    setErrorMessage: (msg) => this.errorMessage = msg,
                    setLoading: (loading) => this.isLoading = loading,
                    setFetched: (fetched) => this.hasFetched = fetched
               });
          }
     }

}
