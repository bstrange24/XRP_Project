import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import * as XRPL from 'xrpl';
import { ValidationUtils } from '../../../utlities/validation-utils';

interface Nft {
  Flags: number;
  Issuer: string;
  NFTokenID: string;
  NFTokenTaxon: number;
  nft_serial: number;
  TransferFee?: number;
}

interface GetNftsApiResponse {
  status: string;
  message: string;
  transactions: Nft[];
  page: number;
  total_pages: number;
  total_count: number;
}

@Component({
  selector: 'app-get-nfts',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  templateUrl: './get-nfts.component.html',
  styleUrls: ['./get-nfts.component.css'],
})
export class GetNftsComponent implements OnInit {
  @ViewChild('scrollContainer') scrollContainer!: ElementRef;

  account: string = '';
  nfts: Nft[] = [];
  page: number = 1;
  pageSize: number = 10;
  totalPages: number = 0;
  totalCount: number = 0;
  isLoading: boolean = false;
  errorMessage: string = '';
  hasFetched: boolean = false;
  displayedColumns: string[] = ['Issuer', 'NFTokenID', 'nft_serial', 'Flags', 'NFTokenTaxon'];

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient
  ) {}

  ngOnInit(): void {}

  async getNfts(reset: boolean = false): Promise<void> {
    if (reset) {
      this.page = 1;
      this.nfts = [];
      this.totalPages = 0;
      this.totalCount = 0;
      this.hasFetched = false;
    }

    if (!this.account.trim() || !ValidationUtils.isValidXrpAddress(this.account)) {
      this.snackBar.open('Please enter a valid XRP account address.', 'Close', {
        duration: 3000,
        panelClass: ['error-snackbar'],
      });
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';

    try {
      const body = {
        account: this.account.trim(),
        page: this.page.toString(),
        page_size: this.pageSize.toString(),
      };
      console.log('Request body:', body);

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<GetNftsApiResponse>('http://127.0.0.1:8000/xrpl/nfts/account/info/', body, { headers })
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success' && Array.isArray(response.transactions)) {
        this.nfts = reset ? response.transactions : [...this.nfts, ...response.transactions];
        if (reset) {
          this.totalPages = response.total_pages;
          this.totalCount = response.total_count;
        }
        console.log('Fetched page:', this.page, 'Total NFTs:', this.nfts.length);

        // Attach scroll listener after first fetch or ensure it’s reattached
        if (this.scrollContainer && !this.scrollContainer.nativeElement.onscroll) {
          const element = this.scrollContainer.nativeElement;
          element.onscroll = () => this.onScroll(); // Direct assignment
          console.log('Scroll listener attached. Container height:', element.clientHeight, 'Scroll height:', element.scrollHeight);
        }

        if (this.scrollContainer) {
          const element = this.scrollContainer.nativeElement;
          console.log('Post-fetch: Container height:', element.clientHeight, 'Scroll height:', element.scrollHeight);
        }
      } else {
        this.nfts = [];
        this.totalPages = 0;
        this.totalCount = 0;
        console.warn('No valid NFTs found in response:', response);
      }

      this.isLoading = false;
      this.hasFetched = true;
    } catch (error: any) {
      this.errorMessage = 'Error fetching NFTs: ' + (error.message || 'Unknown error');
      this.snackBar.open(this.errorMessage, 'Close', {
        duration: 5000,
        panelClass: ['error-snackbar'],
      });
      this.isLoading = false;
      this.hasFetched = true;
    }
  }

  onScroll(): void {
    if (this.isLoading || this.page >= this.totalPages) {
      console.log('Scroll ignored: Loading or last page reached', { page: this.page, totalPages: this.totalPages });
      return;
    }

    const element = this.scrollContainer.nativeElement;
    const scrollTop = element.scrollTop;
    const scrollHeight = element.scrollHeight;
    const clientHeight = element.clientHeight;

    console.log('Scroll event:', { scrollTop, scrollHeight, clientHeight });

    if (scrollHeight - scrollTop - clientHeight < 100) {
      console.log('Scroll triggered: Fetching page', this.page + 1);
      this.page++;
      this.getNfts();
    }
  }

  loadMore(): void {
    if (this.page < this.totalPages && !this.isLoading) {
      console.log('Load more clicked: Fetching page', this.page + 1);
      this.page++;
      this.getNfts();
    }
  }
}