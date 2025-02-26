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

  constructor() {
    // Restore wallet from sessionStorage on service initialization
    const storedWallet = sessionStorage.getItem('xamanWallet');
    if (storedWallet) {
      const wallet = JSON.parse(storedWallet);
      this.walletSubject.next(wallet); // Emit the restored wallet
      console.log('Restored wallet from sessionStorage in WalletService:', wallet);
    } else {
      console.log('No wallet found in sessionStorage.');
    }
  }
  
  // Set the wallet data
  setWallet(wallet: any): void {
    this.walletSubject.next(wallet);
    if (wallet) {
      sessionStorage.setItem('xamanWallet', JSON.stringify(wallet));
    } else {
      sessionStorage.removeItem('xamanWallet');
    }
  }

  // Get the current wallet data
  getWallet(): XamanWalletData | null {
    return this.walletSubject.value;
  }
}