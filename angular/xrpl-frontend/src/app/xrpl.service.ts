import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { HttpClient, HttpParams } from '@angular/common/http';

@Injectable({
  providedIn: 'root'
})
export class XrplService {
  private readonly apiUrl = 'http://localhost:8000/xrpl';
  private readonly apiPaginationUrl = 'http://localhost:8000/xrpl/transaction-history-with-pag/';

  constructor(private readonly http: HttpClient) {}

  getAccountInfo(wallet_address: string): Observable<any> {
    return this.http.get(`${this.apiUrl}/wallet-info/${wallet_address}/`);
  }

  getAccountTransactionHistoryWithPagination(wallet_address: string): Observable<any> {
    return this.http.get(`${this.apiUrl}/transaction-history-with-pag/${wallet_address}/`);
  }

  getAccountTransactionHistoryWithPaginations(wallet_address: string, page: number, pageSize: number = 10): Observable<any> {
    const params = new HttpParams()
      .set('page', page.toString())
      .set('page_size', pageSize.toString());

    const url = `${this.apiPaginationUrl}${wallet_address}/`;
    return this.http.get(url, { params });
  }

  // getTransactionHistory(wallet_address: string): Observable<any> {
    // return this.http.post(`${this.apiUrl}/transaction-history/${wallet_address}/`, {});
  // }

  createAccount(): Observable<any> {
    return this.http.post(`${this.apiUrl}/account/create/`, {});
  }
}
