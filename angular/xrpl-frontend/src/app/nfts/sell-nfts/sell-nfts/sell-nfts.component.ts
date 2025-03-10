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

interface TxJson {
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
}

interface SellNftsApiResponse {
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
    offer_id: string;
  };
}

@Component({
  selector: 'app-sell-nfts',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatCheckboxModule,
  ],
  templateUrl: './sell-nfts.component.html',
  styleUrls: ['./sell-nfts.component.css'],
})
export class SellNftsComponent implements OnInit {
  nftTokenId: string = '';
  sellerSeed: string = '';
  nftokenSellAmount: string = ''; // Remains a string
  checkExistingOffers: boolean = false;
  cancelExistingOffers: boolean = false;
  isLoading: boolean = false;
  errorMessage: string = '';
  hash: string = '';
  txJson: TxJson | null = null;

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient
  ) {}

  ngOnInit(): void {}

  // Validate inputs before submission
  private validateInputs(): boolean {
    if (!this.nftTokenId.trim()) {
      this.snackBar.open('NFT Token ID is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.sellerSeed.trim()) {
      this.snackBar.open('Seller seed is required.', 'Close', { duration: 3000 });
      return false;
    }
    const sellAmount = this.nftokenSellAmount.trim();
    if (!sellAmount || isNaN(+sellAmount) || +sellAmount <= 0) {
      this.snackBar.open('Sell amount must be a positive number.', 'Close', { duration: 3000 });
      return false;
    }
    return true;
  }

  async sellNfts(): Promise<void> {
    if (!this.validateInputs()) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.hash = '';
    this.txJson = null;

    try {
      const body = {
        nft_token_id: this.nftTokenId.trim(),
        seller_seed: this.sellerSeed.trim(),
        nftoken_sell_amount: this.nftokenSellAmount.trim(), // Already a string, trimmed
        check_existing_offers: this.checkExistingOffers ? 'True' : 'False',
        cancel_existing_offers: this.cancelExistingOffers ? 'True' : 'False',
      };

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<SellNftsApiResponse>('http://127.0.0.1:8000/xrpl/nfts/sell/', body, { headers })
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success') {
        this.hash = response.result.hash;
        this.txJson = response.result.tx_json;
        this.snackBar.open(response.message, 'Close', { duration: 5000 });
      } else {
        this.errorMessage = 'Failed to sell NFT.';
        this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      }

      this.isLoading = false;
    } catch (error: any) {
      this.errorMessage = 'Error selling NFT: ' + (error.message || 'Unknown error');
      this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      this.isLoading = false;
    }
  }
}