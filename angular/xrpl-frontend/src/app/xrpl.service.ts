import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { HttpClient, HttpParams } from '@angular/common/http';

@Injectable({
  providedIn: 'root'
})
export class XrplService {
  private apiUrl = 'http://localhost:8000/xrpl';
  private apiPaginationUrl = 'http://localhost:8000/xrpl/transaction-history-with-pag/';

  constructor(private http: HttpClient) {}

  getAccountInfo(accountId: string): Observable<any> {
    return this.http.get(`${this.apiUrl}/account-info/${accountId}/`);
  }

  getAccountTransactionHistoryWithPagination(accountId: string): Observable<any> {
    return this.http.get(`${this.apiUrl}/transaction-history-with-pag/${accountId}/`);
  }

  getAccountTransactionHistoryWithPaginations(account: string, page: number = 1, pageSize: number = 10): Observable<any> {
    const params = new HttpParams()
      .set('page', page.toString())
      .set('page_size', pageSize.toString());

    // Append the account to the URL
    const url = `${this.apiPaginationUrl}${account}/`;

    return this.http.post(url, { params });
  }

  createAccount(): Observable<any> {
    return this.http.post(`${this.apiUrl}/account/create/`, {});
  }
}
