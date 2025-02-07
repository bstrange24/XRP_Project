import { Component, OnInit} from '@angular/core';
import { DatePipe, CommonModule } from '@angular/common';
// import { ActivatedRoute, RouterModule } from '@angular/router';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { TransactionService } from '../transaction.service'; 

@Component({
  selector: 'app-transaction-detail',
  templateUrl: './transaction-detail.component.html',
  styleUrls: ['./transaction-detail.component.css'],
  providers: [DatePipe],
  // imports: [CommonModule, RouterModule],
  imports: [CommonModule, RouterModule,],
  standalone: true,
})
export class TransactionDetailComponent implements OnInit {
  wallet_address: any;
  transactionData: any;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly datePipe: DatePipe,
    private readonly transactionService: TransactionService 
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
