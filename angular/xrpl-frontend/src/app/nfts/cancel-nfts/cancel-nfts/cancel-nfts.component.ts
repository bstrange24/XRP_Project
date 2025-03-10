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

interface CancelNftsApiResponse {
  status: string;
  message: string;
}

@Component({
  selector: 'app-cancel-nfts',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  templateUrl: './cancel-nfts.component.html',
  styleUrls: ['./cancel-nfts.component.css'],
})
export class CancelNftsComponent implements OnInit {
  issuerSeed: string = '';
  nftTokenId: string = '';
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
    if (!this.issuerSeed.trim()) {
      this.snackBar.open('Issuer seed is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.nftTokenId.trim()) {
      this.snackBar.open('NFT Token ID is required.', 'Close', { duration: 3000 });
      return false;
    }
    return true;
  }

  async cancelNfts(): Promise<void> {
    if (!this.validateInputs()) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.successMessage = '';

    try {
      const body = {
        issuer_seed: this.issuerSeed.trim(),
        nft_token_id: this.nftTokenId.trim(),
      };

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<CancelNftsApiResponse>('http://127.0.0.1:8000/xrpl/nfts/cancel/', body, { headers })
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success') {
        this.successMessage = response.message;
        this.snackBar.open(this.successMessage, 'Close', { duration: 5000 });
      } else {
        this.errorMessage = 'Failed to cancel NFT offer.';
        this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      }

      this.isLoading = false;
    } catch (error: any) {
      this.errorMessage = 'Error cancelling NFT: ' + (error.message || 'Unknown error');
      this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      this.isLoading = false;
    }
  }
}