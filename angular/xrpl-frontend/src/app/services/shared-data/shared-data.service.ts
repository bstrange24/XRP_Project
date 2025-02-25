// services/shared-data.service.ts
import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class SharedDataService {
  private readonly walletAddressSubject = new BehaviorSubject<string>('');
  walletAddress$ = this.walletAddressSubject.asObservable();

  private readonly transactionHashSubject = new BehaviorSubject<string>('');
  transactionHash$ = this.transactionHashSubject.asObservable();

  private readonly ledgerIndexSubject = new BehaviorSubject<string>('');
  ledgerIndex$ = this.ledgerIndexSubject.asObservable();

  private readonly newAccountSubject = new BehaviorSubject<any | null>(null);
  newAccount$ = this.newAccountSubject.asObservable();

  setWalletAddress(address: string) {
    this.walletAddressSubject.next(address);
  }

  setTransactionHashSubject(tx_hash: string) {
    this.transactionHashSubject.next(tx_hash);
  }

  setLedgerIndex(ledger_index: string) {
    this.ledgerIndexSubject.next(ledger_index);
  }

  setNewAccount(account: any): void {
    this.newAccountSubject.next(account);
  }

  clearNewAccount(): void {
    this.newAccountSubject.next(null);
  }
}
