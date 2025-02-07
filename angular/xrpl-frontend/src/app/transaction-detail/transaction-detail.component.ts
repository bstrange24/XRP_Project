import { Component, OnInit} from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { XrplService } from '../xrpl.service';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-transaction-detail',
  templateUrl: './transaction-detail.component.html',
  providers: [DatePipe],
  imports: [CommonModule],
  standalone: true,
  styleUrls: ['./transaction-detail.component.css']
})
export class TransactionDetailComponent implements OnInit {
  transaction: any;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly xrplService: XrplService,
    private readonly datePipe: DatePipe
  ) {}

  ngOnInit(): void {
    const wallet_address = this.route.snapshot.paramMap.get('id'); // Get the transaction ID from the route
    if (wallet_address) {
      this.xrplService.getTransactionHistory(wallet_address).subscribe((data) => {
        this.transaction = data;
      });
    }
  }
}
