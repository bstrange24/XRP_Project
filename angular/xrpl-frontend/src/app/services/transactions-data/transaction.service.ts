import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class TransactionService {
  private readonly apiUrl = 'http://localhost:8000/xrpl';

  constructor(private readonly http: HttpClient) {}

  // Fetch transaction data for a specific accountId
  getTransactionHistory(wallet_address: string): Observable<any> {
    console.log(`API URL: ${this.apiUrl}/transaction-history/${wallet_address}/`);
    return this.http.get(`${this.apiUrl}/transaction-history/${wallet_address}/`);
  }
}
