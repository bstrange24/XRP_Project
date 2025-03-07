import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { HttpClient, HttpParams, HttpHeaders } from '@angular/common/http';

@Injectable({
     providedIn: 'root'
})
export class XrplService {
     private readonly apiUrl = 'http://localhost:8000/xrpl';
     constructor(private readonly http: HttpClient) { }

     getAccountInfo(account: string, bodyData: any): Observable<any> {
          const headers = new HttpHeaders({
               'Content-Type': 'application/json',
          });

          console.log('body:' + bodyData);
          return this.http.post(`${this.apiUrl}/account/info/`, bodyData, {
               headers,
          });
     }

     getAccountTransactionHistoryWithPagination(account: string, bodyData: any): Observable<any> {
          const headers = new HttpHeaders({
               'Content-Type': 'application/json',
          });

          console.log('body:' + bodyData);
          return this.http.post(`${this.apiUrl}/transaction/history/`, bodyData, {
               headers,
          });
     }

     getAccountAssets(account: string, bodyData: any): Observable<any> {
          const headers = new HttpHeaders({
               'Content-Type': 'application/json',
          });

          console.log('body:' + bodyData);
          console.log('body:' + bodyData);
          return this.http.post(`${this.apiUrl}/nfts/account/info/`, bodyData, {
               headers,
          });
     }

     getAccountTransactionHistoryWithPaginations(wallet_address: string, page: number, pageSize: number = 10, bodyData: any): Observable<any> {
          const headers = new HttpHeaders({
               'Content-Type': 'application/json',
          });
          console.log('body:' + bodyData);
          return this.http.post(`${this.apiUrl}/transaction/history/`, bodyData, {
               headers,
          });
     }

     getAccountNftsWithPaginations(wallet_address: string, page: number, pageSize: number = 10, bodyData: any): Observable<any> {
          const headers = new HttpHeaders({
               'Content-Type': 'application/json',
          });
          console.log('body:' + bodyData);
          return this.http.post(`${this.apiUrl}/nfts/account/info/`, bodyData, {
               headers,
          });
     }

     createAccount(): Observable<any> {
          // Create HttpParams with the ledger_index query parameter
          return this.http.get(`${this.apiUrl}/account/create/test-account/`, {});
     }

     getLedgerInfo(ledgerIndex: string): Observable<any> {
          const bodyData = {
               ledger_index: ledgerIndex
          };

          const headers = new HttpHeaders({
               'Content-Type': 'application/json',
          });

          return this.http.post(`${this.apiUrl}/ledger/ledger-info/`, bodyData, {
               headers,
          });

          // Create HttpParams with the ledger_index query parameter
          // let params = new HttpParams().set('ledger_index', ledgerIndex);

          // Make the HTTP GET request with the query parameter
          // return this.http.get(`${this.apiUrl}/ledger/ledger-info/`, { 
          // params,
          // headers: new HttpHeaders().set('Authorization', 'Bearer your-token'), // Example if API requires auth
          //  });
     }

     getServerInfo(): Observable<any> {
          return this.http.get(`${this.apiUrl}/ledger/server-info/`);
     }

     getXrpReserveForAccount(account: string): Observable<any> {
          // Create HttpParams with the ledger_index query parameter
          let params = new HttpParams().set('account', account);

          // Make the HTTP GET request with the query parameter
          return this.http.get(`${this.apiUrl}/ledger/xrp-reserves/`, {
               params,
               // headers: new HttpHeaders().set('Authorization', 'Bearer your-token'), // Example if API requires auth
          });
     }

     getTransactionStatusForAccount(tx_hash: string): Observable<any> {
          // Create HttpParams with the ledger_index query parameter
          let params = new HttpParams().set('tx_hash', tx_hash);

          // Make the HTTP GET request with the query parameter
          return this.http.get(`${this.apiUrl}/transaction/status/`, {
               params,
               // headers: new HttpHeaders().set('Authorization', 'Bearer your-token'), // Example if API requires auth
          });
     }

     getAccountBalanceInfo(account: string): Observable<any> {
          // Create HttpParams with the ledger_index query parameter
          let params = new HttpParams().set('account', account);

          // Make the HTTP GET request with the query parameter
          return this.http.get(`${this.apiUrl}/account/balance/`, {
               params,
               // headers: new HttpHeaders().set('Authorization', 'Bearer your-token'), // Example if API requires auth
          });
     }

     getAccountConfigurationInfo(account: string): Observable<any> {
          // Create HttpParams with the ledger_index query parameter
          let params = new HttpParams().set('account', account);

          console.log('I:M HERE 2-----------------------')
          // Make the HTTP GET request with the query parameter
          return this.http.get(`${this.apiUrl}/account/config/`, {
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
               .set('asf_account_txn_id', asf_account_txn_id)
               .set('asf_allow_trustline_clawback', asf_allow_trustline_clawback)
               .set('asf_authorized_nftoken_minter', asf_authorized_nftoken_minter)
               .set('asf_default_ripple', asf_default_ripple)
               .set('asf_deposit_auth', asf_deposit_auth)
               .set('asf_disable_master', asf_disable_master)
               .set('asf_disable_incoming_check', asf_disable_incoming_check)
               .set('asf_disable_incoming_nftoken_offer', asf_disable_incoming_nftoken_offer)
               .set('asf_disable_incoming_paychan', asf_disable_incoming_paychan)
               .set('asf_disable_incoming_trustline', asf_disable_incoming_trustline)
               .set('asf_disallow_XRP', asf_disallow_XRP)
               .set('asf_global_freeze', asf_global_freeze)
               .set('asf_no_freeze', asf_no_freeze)
               .set('asf_require_auth', asf_require_auth)
               .set('asf_require_dest', asf_require_dest)

          console.log('I:M HERE 3-----------------------')
          // Make the HTTP GET request with the query parameter
          return this.http.get(`${this.apiUrl}/account/config/update/`, {
               params,
               // headers: new HttpHeaders().set('Authorization', 'Bearer your-token'), // Example if API requires auth
          });
     }
}