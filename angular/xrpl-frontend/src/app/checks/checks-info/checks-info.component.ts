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

interface SendMax {
  currency: string;
  issuer: string;
  value: string;
}

interface Check {
  Account: string;
  Destination: string;
  Expiration: number;
  Flags: number;
  LedgerEntryType: string;
  OwnerNode: string;
  PreviousTxnID: string;
  PreviousTxnLgrSeq: number;
  SendMax: SendMax;
  Sequence: number;
  index: string;
}

interface ChecksInfoApiResponse {
  status: string;
  message: string;
  checks: Check[];
  page: number;
  total_pages: number;
  total_count: number;
}

@Component({
  selector: 'app-checks-info',
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
  templateUrl: './checks-info.component.html',
  styleUrls: ['./checks-info.component.css'],
})
export class ChecksInfoComponent implements OnInit {
  accountSeed: string = '';
  page: number = 1; // 1-based indexing to match API
  pageSize: number = 10;
  isLoading: boolean = false;
  errorMessage: string = '';
  checks: Check[] = [];
  totalPages: number = 1;
  totalCount: number = 0;
  displayedColumns: string[] = ['Account', 'Destination', 'Expiration', 'SendMax', 'Sequence', 'index'];

  // XRPL epoch offset (seconds from Unix epoch to XRPL epoch: Jan 1, 2000)
  private readonly XRPL_EPOCH_OFFSET = 946684800;

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient
  ) {}

  ngOnInit(): void {}

  // Validate inputs before submission
  private validateInputs(): boolean {
    if (!this.accountSeed.trim()) {
      this.snackBar.open('Account seed is required.', 'Close', { duration: 3000 });
      return false;
    }
    if (!this.isValidXrpSeed(this.accountSeed.trim())) {
      this.snackBar.open('Account seed must be a valid XRP seed.', 'Close', { duration: 3000 });
      return false;
    }
    if (this.page < 1) {
      this.snackBar.open('Page must be at least 1.', 'Close', { duration: 3000 });
      return false;
    }
    if (this.pageSize < 1) {
      this.snackBar.open('Page size must be at least 1.', 'Close', { duration: 3000 });
      return false;
    }
    return true;
  }

  // Validate XRP seed (basic check)
  private isValidXrpSeed(seed: string): boolean {
    try {
      return seed.startsWith('sEd') && seed.length >= 29 && seed.length <= 35;
    } catch (error) {
      console.error('Error validating XRP seed:', error);
      return false;
    }
  }

  async getChecks(): Promise<void> {
    if (!this.validateInputs()) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.checks = [];

    try {
      const body = {
        account_seed: this.accountSeed.trim(),
        page: String(this.page), // API expects string
        page_size: String(this.pageSize), // API expects string
      };

      const headers = new HttpHeaders({
        'Content-Type': 'application/json',
      });

      const response = await firstValueFrom(
        this.http.post<ChecksInfoApiResponse>('http://127.0.0.1:8000/xrpl/checks/get/page', body, { headers })
      );

      console.log('Raw response:', response);

      if (response && response.status === 'success') {
        this.checks = response.checks;
        this.page = response.page;
        this.totalPages = response.total_pages;
        this.totalCount = response.total_count;
        this.snackBar.open(response.message, 'Close', { duration: 5000 });
      } else {
        this.errorMessage = 'Failed to retrieve checks.';
        this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      }

      this.isLoading = false;
    } catch (error: any) {
      this.errorMessage = 'Error retrieving checks: ' + (error.message || 'Unknown error');
      this.snackBar.open(this.errorMessage, 'Close', { duration: 5000 });
      this.isLoading = false;
    }
  }

  // Handle pagination events
  onPageChange(event: PageEvent): void {
    this.page = event.pageIndex + 1; // Convert 0-based index to 1-based page
    this.pageSize = event.pageSize;
    this.getChecks();
  }

  // Format XRPL timestamp to local date string
  formatDate(xrplTimestamp: number): string {
    const unixTimestamp = xrplTimestamp + this.XRPL_EPOCH_OFFSET; // Adjust to Unix epoch
    const date = new Date(unixTimestamp * 1000); // Convert seconds to milliseconds
    return date.toLocaleString();
  }

  // Format SendMax value to 2 decimal places
  formatSendMaxValue(value: string): string {
    const num = parseFloat(value);
    return isNaN(num) ? value : num.toFixed(2);
  }
}