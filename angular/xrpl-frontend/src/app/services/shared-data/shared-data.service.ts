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

  setWalletAddress(address: string) {
    this.walletAddressSubject.next(address);
  }

  setTransactionHashSubject(tx_hash: string) {
    this.transactionHashSubject.next(tx_hash);
  }
}