import { Component, OnInit} from '@angular/core';
import { DatePipe, CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { TransactionService } from '../services/transactions-data/transaction.service'; 
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatTableModule } from '@angular/material/table';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatMenuModule } from '@angular/material/menu';
import { MatSelectModule } from '@angular/material/select';
import { MatOptionModule } from '@angular/material/core';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-transaction-detail',
  templateUrl: './transaction-detail.component.html',
  styleUrls: ['./transaction-detail.component.css'],
  providers: [DatePipe],
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatExpansionModule,
    MatTableModule,
    MatPaginatorModule,
    MatToolbarModule,
    MatMenuModule,
    MatSelectModule,
    MatOptionModule,
    MatIconModule,
    RouterModule,
  ],
  standalone: true,
})
export class TransactionDetailComponent implements OnInit {
  wallet_address: any;
  transactionData: any;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly datePipe: DatePipe,
    private readonly transactionService: TransactionService,
    private readonly snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    console.log('TransactionDetailComponent initialized');
    this.route.paramMap.subscribe((params) => {
      const wallet_address = params.get('wallet_address');
      console.log('Received wallet_address:', wallet_address); // Log the received wallet address
      if (wallet_address) {
        this.wallet_address = wallet_address;
        this.fetchTransactionData(wallet_address); // Call the service if wallet_address is valid
      } else {
        console.error('Account ID not found');
      }
    });
  }

   // Fetch transaction data from the backend
   fetchTransactionData(wallet_address: string): void {
    console.log('Making API call with wallet_address:', wallet_address); // Check if the method is called

    this.transactionService.getTransactionHistory(wallet_address).subscribe(
      (data) => {
        this.transactionData = data; // Store the response in the component's property
        console.log('Transaction data:', this.transactionData); // Check the data in the console
      },
      (error) => {
        console.error('Error fetching transaction data:', error);
      }
    );
  }
}
