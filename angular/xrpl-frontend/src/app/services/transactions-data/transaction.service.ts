import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class TransactionService {
  private readonly apiUrl = 'http://localhost:8000/xrpl';

  constructor(private readonly http: HttpClient) { }

  getTransactionHistory(wallet_address: string, transaction_hash: string): Observable<any> {
    return this.http.get(`${this.apiUrl}/transaction-history/${wallet_address}/${transaction_hash}/`);
  }
}
