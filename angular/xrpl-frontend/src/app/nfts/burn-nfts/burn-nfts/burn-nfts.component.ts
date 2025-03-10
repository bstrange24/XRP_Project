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

interface TxJson {
  Account: string;
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

interface BurnNftsApiResponse {
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
  };
}

@Component({
  selector: 'app-burn-nfts',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  templateUrl: './burn-nfts.component.html',
  styleUrls: ['./burn-nfts.component.css'],
})
export class BurnNftsComponent implements OnInit {
  minterSeed: string = '';
  nftTokenId: string = '';
  isLoading: boolean = false;
  errorMessage: string = '';
  txJson: TxJson | null = null;

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient
  ) {}

  ngOnInit(): void {}

  // Validate inputs before submission
  private validateInputs(): boolean {
    if (!this.minterSeed.trim()) {
      this.snackBar.open('Minter seed is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.nftTokenId.trim()) {
      this.snackBar.open('NFT Token ID is required.', 'Close', { duration: 3000 });
      return false;
    }
    return true;
  }

  async burnNfts(): Promise<void> {
    if (!this.validateInputs()) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.txJson = null;

    try {
      const body = {
        minter_seed: this.minterSeed.trim(),
        nft_token_id: this.nftTokenId.trim(),
      };

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<BurnNftsApiResponse>('http://127.0.0.1:8000/xrpl/nfts/burn/', body, { headers })
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success') {
        this.txJson = response.result.tx_json;
        this.snackBar.open(response.message, 'Close', { duration: 5000 });
      } else {
        this.errorMessage = 'Failed to burn NFT.';
        this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      }

      this.isLoading = false;
    } catch (error: any) {
      this.errorMessage = 'Error burning NFT: ' + (error.message || 'Unknown error');
      this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      this.isLoading = false;
    }
  }
}