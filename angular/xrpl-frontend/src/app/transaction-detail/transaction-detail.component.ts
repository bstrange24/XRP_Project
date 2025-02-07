import { Component, OnInit} from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { XrplService } from '../xrpl.service';

@Component({
  selector: 'app-transaction-detail',
  templateUrl: './transaction-detail.component.html',
  providers: [DatePipe],
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
    const txId = this.route.snapshot.paramMap.get('id'); // Get the transaction ID from the route
    if (txId) {
      this.xrplService.getTransactionHistory(txId).subscribe((data) => {
        this.transaction = data;
      });
    }
  }
}
