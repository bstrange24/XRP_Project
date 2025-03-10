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
import { MatTableModule } from '@angular/material/table';

interface MintedNft {
     NFTokenID: string;
     NFTokenTaxon: number;
     sell_result?: {
          hash: string;
          offer_id: string;
          tx_json: {
               Account: string;
               Amount: string;
               Fee: string;
               Flags: number;
               LastLedgerSequence: number;
               NFTokenID: string;
               Sequence: number;
               SigningPubKey: string;
               TransactionType: string;
               TxnSignature: string;
               date: number;
               ledger_index: number;
          };
     };
}

interface MintNftsApiResponse {
     status: string;
     message: string;
     minted_nfts: MintedNft[];
     failed_mints: any[];
}

@Component({
     selector: 'app-mint-nfts',
     standalone: true,
     imports: [
          CommonModule,
          FormsModule,
          MatCardModule,
          MatFormFieldModule,
          MatInputModule,
          MatButtonModule,
          MatCheckboxModule,
          MatTableModule,
     ],
     templateUrl: './mint-nfts.component.html',
     styleUrls: ['./mint-nfts.component.css'],
})
export class MintNftsComponent implements OnInit {
     minterSeed: string = '';
     txFlagsOptions: string[] = ['TF_TRANSFERABLE', 'TF_BURNABLE', 'TF_ONLY_XRP'];
     txFlags: string[] = [];
     mintOnly: boolean = false;
     mintAndSell: boolean = false;
     sellAmountsInput: string = '';
     nftCount: number = 1;
     transferFee: number = 0;
     isLoading: boolean = false;
     errorMessage: string = '';
     mintedNfts: MintedNft[] = [];
     displayedColumns: string[] = [
          'NFTokenID',
          'NFTokenTaxon',
          'SellHash',
          'SellOfferId',
          'SellAccount',
          'SellAmount',
     ];

     constructor(
          private readonly snackBar: MatSnackBar,
          private readonly http: HttpClient
     ) { }

     ngOnInit(): void { }

     onMintOnlyChange(checked: boolean): void {
          if (checked) {
               this.mintOnly = true;
               this.mintAndSell = false;
               this.sellAmountsInput = '';
          }
     }

     onMintAndSellChange(checked: boolean): void {
          if (checked) {
               this.mintAndSell = true;
               this.mintOnly = false;
          }
     }

     addFlag(flag: string): void {
          this.txFlags.push(flag);
     }

     removeFlag(index: number): void {
          this.txFlags.splice(index, 1);
     }

     private resetForm(): void {
          this.minterSeed = '';
          this.txFlags = [];
          this.mintOnly = false;
          this.mintAndSell = false;
          this.sellAmountsInput = '';
          this.nftCount = 1;
          this.transferFee = 0;
     }

     private getSellAmountsArray(): number[] {
          if (!this.sellAmountsInput.trim()) return [];
          return this.sellAmountsInput.split(',').map(val => parseInt(val.trim(), 10));
     }

     private validateInputs(): boolean {
          if (!this.minterSeed.trim()) {
               this.snackBar.open('Minter seed is required.', 'Close', { duration: 3000 });
               return false;
          }
          if (this.txFlags.length === 0) {
               this.snackBar.open('At least one transaction flag is required.', 'Close', { duration: 3000 });
               return false;
          }
          if (!this.mintOnly && !this.mintAndSell) {
               this.snackBar.open('Select either "Mint Only" or "Mint and Sell".', 'Close', { duration: 3000 });
               return false;
          }
          if (this.nftCount < 1 || !Number.isInteger(this.nftCount)) {
               this.snackBar.open('NFT count must be a positive integer.', 'Close', { duration: 3000 });
               return false;
          }
          if (this.txFlags.length !== this.nftCount) {
               this.snackBar.open('Number of flags must match NFT count.', 'Close', { duration: 3000 });
               return false;
          }
          if (this.transferFee < 0 || this.transferFee > 50000 || this.transferFee % 1 !== 0) {
               this.snackBar.open('Transfer fee must be between 0 and 50,000 (0.000% to 50.000%) in whole basis points.', 'Close', { duration: 3000 });
               return false;
          }
          if (this.mintAndSell) {
               const sellAmounts = this.getSellAmountsArray();
               if (sellAmounts.length !== this.nftCount) {
                    this.snackBar.open('Number of sell amounts must match NFT count.', 'Close', { duration: 3000 });
                    return false;
               }
               if (sellAmounts.some(amount => isNaN(amount) || amount <= 0)) {
                    this.snackBar.open('All sell amounts must be positive numbers.', 'Close', { duration: 3000 });
                    return false;
               }
          }
          return true;
     }

     async mintNfts(): Promise<void> {
          if (!this.validateInputs()) return;

          this.isLoading = true;
          this.errorMessage = '';
          this.mintedNfts = [];

          try {
               const body: any = {
                    minter_seed: this.minterSeed.trim(),
                    tx_flags: this.txFlags,
                    nft_count: this.nftCount,
                    transfer_fee: this.transferFee,
               };
               if (this.mintOnly) {
                    body.mint_and_sell = 'False';
               } else if (this.mintAndSell) {
                    body.mint_and_sell = 'True';
                    body.sell_amounts = this.getSellAmountsArray();
               }

               const headers = new HttpHeaders({
                    'Content-Type': 'application/json',
               });

               const response = await firstValueFrom(
                    this.http.post<MintNftsApiResponse>('http://127.0.0.1:8000/xrpl/nfts/mint/', body, { headers })
               );

               console.log('Raw response:', response);

               if (response && response.status === 'success') {
                    this.mintedNfts = response.minted_nfts;
                    this.snackBar.open(response.message, 'Close', { duration: 3000 });
                    this.resetForm();
               } else {
                    this.errorMessage = 'Failed to mint NFTs.';
                    this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
               }

               this.isLoading = false;
          } catch (error: any) {
               this.errorMessage = 'Error minting NFTs: ' + (error.message || 'Unknown error');
               this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
               this.isLoading = false;
          }
     }
}