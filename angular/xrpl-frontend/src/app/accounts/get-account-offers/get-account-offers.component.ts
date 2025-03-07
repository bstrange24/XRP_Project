import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator'; // For pagination
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpParams, HttpHeaders } from '@angular/common/http';
import * as XRPL from 'xrpl';
import { firstValueFrom } from 'rxjs';
import { WalletService } from '../../services/wallet-services/wallet.service';

// Define the interface for the API response
interface AccountOffersResponse {
  status: string;
  message: string;
  offers: {
    flags: number;
    quality: string;
    seq: number;
    taker_gets: string;
    taker_pays: {
      currency: string;
      issuer: string;
      value: string;
    };
  }[];
  page: number;
  total_pages: number;
  total_offers: number;
}

interface XamanWalletData {
  address: string;
  seed?: string; // Optional, as Xaman doesn’t expose seeds
}

@Component({
  selector: 'app-get-account-offers',
  standalone: true,
  imports: [CommonModule, FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatTableModule, MatPaginatorModule],
  templateUrl: './get-account-offers.component.html',
  styleUrls: ['./get-account-offers.component.css']
})
export class GetAccountOffersComponent implements OnInit {
  account: string = '';
  offers: any[] = [];
  totalOffers: number = 0;
  currentPage: number = 1;
  pageSize: number = 10;
  isLoading: boolean = false;
  errorMessage: string = '';
  displayedColumns: string[] = ['flags', 'quality', 'seq', 'taker_gets', 'taker_pays_currency', 'taker_pays_issuer', 'taker_pays_value'];
  connectedWallet: XamanWalletData | null = null;
  hasFetched: boolean = false;

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient,
    private readonly walletService: WalletService
  ) {}

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

  async getAccountOffers(): Promise<void> {
    this.isLoading = true;
    this.errorMessage = '';
    this.offers = [];

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


      const params = new HttpParams()
        .set('account', this.account.trim())
        .set('page', this.currentPage.toString())
        .set('page_size', this.pageSize.toString());

      const response = await firstValueFrom(this.http.get<AccountOffersResponse>('http://127.0.0.1:8000/xrpl/get-account-offers/', { params }));
      this.offers = response.offers || [];
      this.totalOffers = response.total_offers || 0;
      this.isLoading = false;
      this.hasFetched = true;
      console.log('Account offers retrieved:', response);
    } catch (error: any) {
      console.error('Error retrieving account offers:', error);
      let errorMessage: string;
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error as any).message;
      } else {
        errorMessage = 'An unexpected error occurred while retrieving account offers.';
      }
      this.errorMessage = errorMessage;
      this.snackBar.open(this.errorMessage, 'Close', {
        duration: 3000,
        panelClass: ['error-snackbar']
      });
      this.isLoading = false;
      this.hasFetched = true;
    }
  }

  onPageChange(event: PageEvent): void {
    this.currentPage = event.pageIndex + 1;
    this.pageSize = event.pageSize;
    this.getAccountOffers();
  }
}