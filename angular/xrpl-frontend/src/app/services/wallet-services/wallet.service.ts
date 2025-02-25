// src/app/services/wallet.service.ts
import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

// Define the wallet data interface
interface XamanWalletData {
  address: string;
  seed?: string; // Optional, as Xaman doesn’t expose seeds
}

@Injectable({
  providedIn: 'root'
})
export class WalletService {
  private readonly walletSubject = new BehaviorSubject<XamanWalletData | null>(null);
  wallet$ = this.walletSubject.asObservable();

  // Set the wallet data
  setWallet(wallet: XamanWalletData | null): void {
    this.walletSubject.next(wallet);
  }

  // Get the current wallet data
  getWallet(): XamanWalletData | null {
    return this.walletSubject.value;
  }
}