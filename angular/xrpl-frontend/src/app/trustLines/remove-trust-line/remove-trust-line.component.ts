import { Component, OnInit, OnDestroy } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Subscription } from 'rxjs';
import { WalletService } from '../../services/wallet-services/wallet.service';

interface TrustSetPayload {
  txjson: {
    TransactionType: 'TrustSet';
    Account: string;
    LimitAmount: {
      currency: string;
      issuer: string;
      value: string;
    };
  };
}

interface XummPayloadResult {
  meta: {
    signed: boolean;
    cancelled: boolean;
    exists?: boolean;
    account?: string;
  };
  payload?: {
    Account?: string;
  };
  response: {
    txid: string;
    account?: string;
  };
  account?: string;
}

interface XamanWalletData {
  address: string;
  seed?: string;
}

@Component({
  selector: 'app-remove-trust-line',
  standalone: true,
  imports: [CommonModule, FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  templateUrl: './remove-trust-line.component.html',
  styleUrls: ['./remove-trust-line.component.css']
})
export class RemoveTrustLineComponent implements OnInit, OnDestroy {
  issuerAddress: string = '';
  currencyCode: string = '';
  trustLineResult: { status: string; message?: string; result?: { hash: string; tx_json: any } } | null = null;
  isLoading: boolean = false;
  private walletSubscription!: Subscription; // Add ! to assert it will be assigned

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient,
    private readonly walletService: WalletService
  ) {
    console.log('Constructor called');
    console.log('Initial state:', { isLoading: this.isLoading, wallet: this.walletService.getWallet() });
    console.log('Remove button disabled:', this.isLoading || !this.walletService.getWallet()?.address);
  }

  ngOnInit(): void {
    this.walletSubscription = this.walletService.wallet$.subscribe((wallet: XamanWalletData | null) => {
      console.log('Wallet updated:', wallet);
      console.log('Remove button disabled after update:', this.isLoading || !wallet?.address);
    });
  }

  ngOnDestroy(): void {
    this.walletSubscription.unsubscribe();
  }

  async connectWallet(): Promise<void> {
    try {
      const signInPayload: { txjson: { TransactionType: 'SignIn' } } = { txjson: { TransactionType: 'SignIn' } };
      const response = await this.http.post<any>('http://localhost:3000/api/xumm/payload', signInPayload, {
        headers: {
          'X-API-Key': '93b47736-fd5d-4d16-968f-c1c565c8e54f',
          'X-API-Secret': '3a89cac1-613b-49b5-b125-1d1a8ba3b35b',
        },
      }).toPromise();

      if (response) {
        window.open(response.next.always, '_blank');
        const checkStatus = async (uuid: string) => {
          const status = await this.http.get<any>(`http://localhost:3000/api/xumm/payload/${uuid}`, {
            headers: {
              'X-API-Key': '93b47736-fd5d-4d16-968f-c1c565c8e54f',
              'X-API-Secret': '3a89cac1-613b-49b5-b125-1d1a8ba3b35b',
            },
          }).toPromise();

          console.log('Wallet connection status:', JSON.stringify(status, null, 2));

          if (status?.meta?.signed) {
            const accountAddress = status.payload?.Account || status.account || status.response?.account || status.meta?.account;
            console.log('Setting wallet with address:', accountAddress);
            this.walletService.setWallet({ address: accountAddress || '' });
            if (!accountAddress) {
              console.error('No account address found in status:', status);
            }
            this.snackBar.open('Wallet connected!', 'Close', { duration: 3000 });
          } else if (status?.meta?.cancelled || (status?.meta?.exists === false)) {
            this.snackBar.open('Wallet connection rejected or expired.', 'Close', { duration: 3000 });
          } else {
            setTimeout(() => checkStatus(uuid), 1000);
          }
        };
        checkStatus(response.uuid);
      }
    } catch (error: any) {
      this.snackBar.open('Error connecting wallet.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
    }
  }

  async removeTrustLine(): Promise<void> {
    console.log('Wallet state before removeTrustLine:', this.walletService.getWallet());
    this.isLoading = true;
    this.trustLineResult = null;

    const wallet = this.walletService.getWallet();
    if (!wallet?.address) {
      this.snackBar.open('Please connect your wallet first.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }
    if (!this.issuerAddress.trim() || !this.isValidXrpAddress(this.issuerAddress)) {
      this.snackBar.open('Please enter a valid issuer XRP address.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }
    if (!this.currencyCode.trim() || !this.isValidCurrencyCode(this.currencyCode)) {
      this.snackBar.open('Please enter a valid 3-character currency code (e.g., USD).', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
      return;
    }

    const payload: TrustSetPayload = {
      txjson: {
        TransactionType: 'TrustSet',
        Account: wallet.address,
        LimitAmount: {
          currency: this.currencyCode.trim(),
          issuer: this.issuerAddress.trim(),
          value: '0',
        },
      },
    };

    try {
      const response = await this.http.post<any>('http://localhost:3000/api/xumm/payload', payload, {
        headers: {
          'X-API-Key': '93b47736-fd5d-4d16-968f-c1c565c8e54f',
          'X-API-Secret': '3a89cac1-613b-49b5-b125-1d1a8ba3b35b',
        },
      }).toPromise();

      if (response) {
        window.open(response.next.always, '_blank');

        const checkStatus = async (uuid: string) => {
          const status = await this.http.get<XummPayloadResult>(`http://localhost:3000/api/xumm/payload/${uuid}`, {
            headers: {
              'X-API-Key': '93b47736-fd5d-4d16-968f-c1c565c8e54f',
              'X-API-Secret': '3a89cac1-613b-49b5-b125-1d1a8ba3b35b',
            },
          }).toPromise();

          console.log('Remove trustline status:', JSON.stringify(status, null, 2));

          if (status?.meta?.signed) {
            this.trustLineResult = {
              status: 'success',
              result: {
                hash: status.response.txid,
                tx_json: payload.txjson,
              },
            };
            this.snackBar.open('Trust line removed successfully!', 'Close', { duration: 3000 });
            this.isLoading = false;
          } else if (status?.meta?.cancelled || (status?.meta?.exists === false)) {
            this.trustLineResult = { status: 'error', message: 'User rejected or cancelled the transaction.' };
            this.snackBar.open('User rejected or cancelled the transaction.', 'Close', { duration: 3000 });
            this.isLoading = false;
          } else {
            setTimeout(() => checkStatus(uuid), 2000);
          }
        };

        checkStatus(response.uuid);
      }
    } catch (error: any) {
      this.trustLineResult = { status: 'error', message: error.message || 'Failed to remove trust line.' };
      this.snackBar.open('Error removing trust line.', 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.isLoading = false;
    }
  }

  private isValidXrpAddress(address: string): boolean {
    return /^r[1-9A-HJ-NP-Za-km-z]{25,34}$/.test(address);
  }

  private isValidCurrencyCode(code: string): boolean {
    return /^[A-Z]{3}$/.test(code);
  }
}