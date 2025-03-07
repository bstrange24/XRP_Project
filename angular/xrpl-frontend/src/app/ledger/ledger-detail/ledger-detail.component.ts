import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ActivatedRoute, Router } from '@angular/router';
import { XrplService } from '../../services/xrpl-data/xrpl.service';

@Component({
  selector: 'app-ledger-detail',
  standalone: true,
  imports: [CommonModule, MatCardModule],
  templateUrl: './ledger-detail.component.html',
  styleUrl: './ledger-detail.component.css'
})
export class LedgerDetailComponent implements OnInit {
  ledgerInfo: any | null = null;
  ledger_index: string = '';
  errorMessage: string = '';
  isLoading: boolean = false;

  constructor(
    private readonly xrplService: XrplService,
    private readonly snackBar: MatSnackBar,
    private readonly route: ActivatedRoute,
    private readonly router: Router
  ) {}

  ngOnInit(): void {
    this.route.params.subscribe(params => {
      this.ledger_index = params['ledgerIndex']; // Get ledger_index from the route parameter
      console.log('Ledger Index from Route:', this.ledger_index);
      if (this.ledger_index) {
        this.fetchLedgerData(this.ledger_index);
      } else {
        this.errorMessage = 'No ledger index provided.';
        this.snackBar.open(this.errorMessage, 'Close', {
          duration: 3000,
          panelClass: ['error-snackbar']
        });
      }
    });
  }
 
  fetchLedgerData(ledger_index: string) {
    this.isLoading = true;
    this.errorMessage = '';
    this.xrplService.getLedgerInfo(ledger_index).subscribe(
      (data) => {
        this.ledgerInfo = data;
        this.isLoading = false;
        console.log('Ledger Info Fetched:', data);
      },
      (error) => {
        console.error('Error fetching ledger information:', error);
        this.ledgerInfo = { status: 'error', message: 'Failed to fetch ledger information. Please try again.' };
        this.errorMessage = error.message || 'An error occurred while fetching ledger data.';
        this.snackBar.open(this.errorMessage, 'Close', {
          duration: 3000,
          panelClass: ['error-snackbar']
        });
        this.isLoading = false;
      }
    );
  }
}