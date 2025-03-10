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

interface BuyNftsApiResponse {
  status: string;
  message: string;
}

@Component({
  selector: 'app-buy-nfts',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  templateUrl: './buy-nfts.component.html',
  styleUrls: ['./buy-nfts.component.css'],
})
export class BuyNftsComponent implements OnInit {
  nftTokenId: string = '';
  issuerSeed: string = '';
  buyerSeed: string = '';
  buyOfferAmount: string = ''; // String to match API and avoid trim() issues
  isLoading: boolean = false;
  errorMessage: string = '';
  successMessage: string = '';

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
    if (!this.issuerSeed.trim()) {
      this.snackBar.open('Issuer seed is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.buyerSeed.trim()) {
      this.snackBar.open('Buyer seed is required.', 'Close', { duration: 3000 });
      return false;
    }
    const amount = this.buyOfferAmount.trim();
    if (!amount || isNaN(+amount) || +amount <= 0) {
      this.snackBar.open('Buy offer amount must be a positive number.', 'Close', { duration: 3000 });
      return false;
    }
    return true;
  }

  // Reset specific input fields on success
  private resetForm(): void {
    this.nftTokenId = '';
    this.buyOfferAmount = '';
    // issuerSeed and buyerSeed are not reset as per requirement
  }

  async buyNfts(): Promise<void> {
    if (!this.validateInputs()) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.successMessage = '';

    try {
      const body = {
        nft_token_id: this.nftTokenId.trim(),
        issuer_seed: this.issuerSeed.trim(),
        buyer_seed: this.buyerSeed.trim(),
        buy_offer_amount: this.buyOfferAmount.trim(), // Sent as string per API spec
      };

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<BuyNftsApiResponse>('http://127.0.0.1:8000/xrpl/nfts/buy/', body, { headers })
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success') {
        this.successMessage = response.message;
        this.snackBar.open(this.successMessage, 'Close', { duration: 5000 });
        this.resetForm(); // Reset token ID and buy offer amount on success
      } else {
        this.errorMessage = 'Failed to buy NFT.';
        this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      }

      this.isLoading = false;
    } catch (error: any) {
      this.errorMessage = 'Error buying NFT: ' + (error.message || 'Unknown error');
      this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      this.isLoading = false;
    }
  }
}