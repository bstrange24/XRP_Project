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
    return this.http.get(`${this.apiUrl}/account-info/${wallet_address}/`);
  }

  getAccountTransactionHistoryWithPagination(wallet_address: string): Observable<any> {
    return this.http.get(`${this.apiUrl}/transaction-history-with-pag/${wallet_address}/`);
  }

  getAccountAssets(wallet_address: string): Observable<any> {
    // Create HttpParams with the ledger_index query parameter
    let params = new HttpParams().set('wallet_address', wallet_address);

    // Make the HTTP GET request with the query parameter
    return this.http.get(`${this.apiUrl}/get-account-nft/`, { 
      params,
      // headers: new HttpHeaders().set('Authorization', 'Bearer your-token'), // Example if API requires auth
     });
  }

  getAccountTransactionHistoryWithPaginations(wallet_address: string, page: number, pageSize: number = 10): Observable<any> {
    const params = new HttpParams()
      .set('page', page.toString())
      .set('page_size', pageSize.toString());

    const url = `${this.apiPaginationUrl}${wallet_address}/`;
    return this.http.get(url, { params });
  }

  createAccount(): Observable<any> {
    // Create HttpParams with the ledger_index query parameter
    return this.http.get(`${this.apiUrl}/create-test-account/`, {});
  }

  getLedgerInfo(ledgerIndex: string): Observable<any> {
    // Create HttpParams with the ledger_index query parameter
    let params = new HttpParams().set('ledger_index', ledgerIndex);

    // Make the HTTP GET request with the query parameter
    return this.http.get(`${this.apiUrl}/get-ledger-info/`, { 
      params,
      // headers: new HttpHeaders().set('Authorization', 'Bearer your-token'), // Example if API requires auth
     });
  }

  getServerInfo(): Observable<any> {
    return this.http.get(`${this.apiUrl}/get-server-info/`);
  }

  getXrpReserveForAccount(wallet_address: string): Observable<any> {
    // Create HttpParams with the ledger_index query parameter
    let params = new HttpParams().set('wallet_address', wallet_address);

    // Make the HTTP GET request with the query parameter
    return this.http.get(`${this.apiUrl}/get-xrp-reserves/`, { 
      params,
      // headers: new HttpHeaders().set('Authorization', 'Bearer your-token'), // Example if API requires auth
     });
  }

  getTransactionStatusForAccount(hash: string): Observable<any> {
    // Create HttpParams with the ledger_index query parameter
    let params = new HttpParams().set('wallet_address', hash);

    // Make the HTTP GET request with the query parameter
    return this.http.get(`${this.apiUrl}/check-transaction-status/`, { 
      params,
      // headers: new HttpHeaders().set('Authorization', 'Bearer your-token'), // Example if API requires auth
     });
  }

  getAccountBalanceInfo(wallet_address: string): Observable<any> {
    // Create HttpParams with the ledger_index query parameter
    let params = new HttpParams().set('wallet_address', wallet_address);

    // Make the HTTP GET request with the query parameter
    return this.http.get(`${this.apiUrl}/check-account-balance/`, { 
      params,
      // headers: new HttpHeaders().set('Authorization', 'Bearer your-token'), // Example if API requires auth
     });
  }

  getAccountConfigurationInfo(wallet_address: string): Observable<any> {
    // Create HttpParams with the ledger_index query parameter
    let params = new HttpParams().set('wallet_address', wallet_address);

    // Make the HTTP GET request with the query parameter
    return this.http.get(`${this.apiUrl}/get-account-config/`, { 
      params,
      // headers: new HttpHeaders().set('Authorization', 'Bearer your-token'), // Example if API requires auth
     });
  }

  updateAccountConfigurationInfo(wallet_seed: string, asf_account_txn_id: boolean, asf_allow_trustline_clawback: boolean, asf_authorized_nftoken_minter: boolean,
    asf_default_ripple: boolean, asf_deposit_auth: boolean, asf_disable_master: boolean, asf_disable_incoming_check: boolean, asf_disable_incoming_nftoken_offer: boolean,
    asf_disable_incoming_paychan: boolean, asf_disable_incoming_trustline: boolean, asf_disallow_XRP: boolean, asf_global_freeze: boolean, asf_no_freeze: boolean,
    asf_require_auth: boolean, asf_require_dest: boolean): Observable<any> {
    // Create HttpParams with the ledger_index query parameter
    let params = new HttpParams()
    .set('wallet_seed', wallet_seed)
    .set('asf_account_txn_id',asf_account_txn_id)
    .set('asf_allow_trustline_clawback',asf_allow_trustline_clawback)
    .set('asf_authorized_nftoken_minter',asf_authorized_nftoken_minter)
    .set('asf_default_ripple',asf_default_ripple)
    .set('asf_deposit_auth',asf_deposit_auth)
    .set('asf_disable_master',asf_disable_master)
    .set('asf_disable_incoming_check',asf_disable_incoming_check)
    .set('asf_disable_incoming_nftoken_offer',asf_disable_incoming_nftoken_offer)
    .set('asf_disable_incoming_paychan',asf_disable_incoming_paychan)
    .set('asf_disable_incoming_trustline',asf_disable_incoming_trustline)
    .set('asf_disallow_XRP',asf_disallow_XRP)
    .set('asf_global_freeze',asf_global_freeze)
    .set('asf_no_freeze',asf_no_freeze)
    .set('asf_require_auth',asf_require_auth)
    .set('asf_require_dest',asf_require_dest)

    // Make the HTTP GET request with the query parameter
    return this.http.get(`${this.apiUrl}/update-account-config/`, { 
      params,
      // headers: new HttpHeaders().set('Authorization', 'Bearer your-token'), // Example if API requires auth
     });
  }
}