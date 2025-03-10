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
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import * as XRPL from 'xrpl';

interface Offer {
  flags: number;
  quality: string;
  seq: number;
  taker_gets: {
    currency: string;
    issuer: string;
    value: string;
  };
  taker_pays: string; // In drops if XRP
}

interface GetAccountOffersApiResponse {
  status: string;
  message: string;
  offers: Offer[];
  page: number;
  total_pages: number;
  total_offers: number;
}

@Component({
  selector: 'app-get-account-offers',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatTableModule,
    MatPaginatorModule,
  ],
  templateUrl: './get-account-offers.component.html',
  styleUrls: ['./get-account-offers.component.css'],
})
export class GetAccountOffersComponent implements OnInit {
  account: string = '';
  isLoading: boolean = false;
  errorMessage: string = '';
  offers: Offer[] = [];
  displayedColumns: string[] = ['flags', 'quality', 'seq', 'takerGets', 'takerPays'];
  totalOffers: number = 0;
  currentPage: number = 1; // API expects 1-based page numbers
  totalPages: number = 1;
  pageSize: number = 10; // Default page size

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient
  ) {}

  ngOnInit(): void {}

  // Validate inputs before submission
  private validateInputs(): boolean {
    if (!this.account.trim()) {
      this.snackBar.open('Account is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.isValidXrpAddress(this.account.trim())) {
      this.snackBar.open('Account must be a valid XRP address.', 'Close', { duration: 3000 });
      return false;
    }
    return true;
  }

  // Validate XRP address
  private isValidXrpAddress(address: string): boolean {
    try {
      return XRPL.isValidAddress(address);
    } catch (error) {
      console.error('Error validating XRP address:', error);
      return false;
    }
  }

  async getAccountOffers(): Promise<void> {
    if (!this.validateInputs()) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.offers = [];

    try {
      const body = {
        account: this.account.trim(),
        page: this.currentPage.toString(),
        page_size: this.pageSize.toString(),
      };

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<GetAccountOffersApiResponse>('http://127.0.0.1:8000/xrpl/account/offers/', body, { headers })
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success') {
        this.offers = response.offers;
        this.currentPage = response.page;
        this.totalPages = response.total_pages;
        this.totalOffers = response.total_offers;
        this.snackBar.open(response.message, 'Close', { duration: 5000 });
      } else {
        this.errorMessage = 'Failed to retrieve account offers.';
        this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      }

      this.isLoading = false;
    } catch (error: any) {
      this.errorMessage = 'Error retrieving account offers: ' + (error.message || 'Unknown error');
      this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      this.isLoading = false;
    }
  }

  // Handle pagination change
  onPageChange(event: PageEvent): void {
    this.currentPage = event.pageIndex + 1; // Convert 0-based index to 1-based page number
    this.pageSize = event.pageSize;
    this.getAccountOffers();
  }

  // Format Taker Pays (assume XRP in drops if no currency specified)
  formatTakerPays(takerPays: string): string {
    const drops = parseFloat(takerPays);
    if (isNaN(drops)) return takerPays;
    const xrp = drops / 1000000; // Convert drops to XRP
    return `${xrp.toFixed(2)} XRP`;
  }
}