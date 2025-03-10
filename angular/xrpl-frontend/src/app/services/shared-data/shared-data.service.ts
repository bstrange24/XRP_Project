// services/shared-data.service.ts
import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { ChangeDetectorRef } from '@angular/core';

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
    console.log('Setting wallet address:', address);
    this.walletAddressSubject.next(address);
  }

  setTransactionHashSubject(tx_hash: string) {
    console.log('Setting transaction hash:', tx_hash)
    this.transactionHashSubject.next(tx_hash);
  }

  setLedgerIndex(ledger_index: string) {
    console.log('Setting ledger index:', ledger_index);
    this.ledgerIndexSubject.next(ledger_index);
  }

  setNewAccount(account: any): void {
    console.log('Setting new account:', account);
    this.newAccountSubject.next(account);
  }

  clearNewAccount(): void {
    this.newAccountSubject.next(null);
  }
}
