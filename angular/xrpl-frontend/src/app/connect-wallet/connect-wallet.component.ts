import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatSnackBarModule, MatSnackBar } from '@angular/material/snack-bar';
import { NgxQrcodeStylingModule } from 'ngx-qrcode-styling';
import { XummSdk } from 'xumm-sdk';
import { HttpClient } from '@angular/common/http';
import { XummService } from '../services/xumm-data/xumm.service';
import { WalletService } from '../services/wallet-services/wallet.service';
import { MatDialog } from '@angular/material/dialog';

// Define interfaces for Xaman wallet data
interface XamanWalletData {
  address: string;
  seed?: string; // Optional, as Xaman doesn’t expose seeds
}

@Component({
  selector: 'app-connect-wallet',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatSnackBarModule,
    NgxQrcodeStylingModule
  ],
  templateUrl: './connect-wallet.component.html',
  styleUrls: ['./connect-wallet.component.css']
})
export class ConnectWalletComponent implements OnInit {
  qrData: string = '';
  connectedWallet: XamanWalletData | null = null;
  isLoading: boolean = false;
  errorMessage: string = '';
  private payloadId: string | null = null;

  // Initialize the Xumm SDK with your API credentials
  private readonly xumm = new XummSdk('93b47736-fd5d-4d16-968f-c1c565c8e54f', '3a89cac1-613b-49b5-b125-1d1a8ba3b35b');

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient,
    private readonly xummService: XummService,
    private readonly cdr: ChangeDetectorRef, // Add ChangeDetectorRef for manual change detection
    private readonly walletService: WalletService
  ) {}

  ngOnInit(): void {}

  // Generate a QR code for Xaman wallet connection
  private async generateQrCode(): Promise<void> {
    this.isLoading = true; // Set loading state before the async call
    this.errorMessage = ''; // Clear any previous error
    console.log('Starting QR code generation... State:', { isLoading: this.isLoading, connectedWallet: this.connectedWallet, qrData: this.qrData });

    try {
      console.log('API Credentials:', {
        apiKey: '93b47736-fd5d-4d16-968f-c1c565c8e54f',
        apiSecret: '3a89cac1-613b-49b5-b125-1d1a8ba3b35b'
      });
      const payload = {
        txjson: {
          TransactionType: 'SignIn' as const
        }
      };

      console.log('Payload:', payload);
      this.xummService.createPayload(payload).subscribe(
        (response) => {
          console.log('Payload created:', response);
          this.qrData = response.next.always || `xaman://connect?payload=${response.uuid}`; // Use next.always or uuid for QR data
          this.payloadId = response.uuid;
          console.log('Generated QR code URL:', this.qrData);
          this.isLoading = false; // Clear loading state on success
          this.snackBar.open('Scan the QR code with Xaman to connect.', 'Close', { duration: 3000 });
          this.cdr.detectChanges(); // Force Angular to detect changes and update the UI
          console.log('After update, State:', { isLoading: this.isLoading, connectedWallet: this.connectedWallet, qrData: this.qrData });
        },
        (error) => {
          console.error('Error creating payload:', error);
          console.error('Error generating QR code:', error);
          this.isLoading = false; // Clear loading state on error
          this.errorMessage = 'Failed to generate QR code for wallet connection. Check Xumm API credentials, network, or proxy.';
          this.snackBar.open(this.errorMessage, 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
          this.cdr.detectChanges(); // Force update on error
          throw error; // Re-throw to see full stack trace
        }
      );
    } catch (error) {
      this.isLoading = false; // Ensure loading is cleared on any error
      console.error('Error generating QR code:', error);
      this.errorMessage = 'Failed to generate QR code for wallet connection. Check Xumm API credentials, network, or proxy.';
      this.snackBar.open(this.errorMessage, 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.cdr.detectChanges(); // Force update on error
      throw error; // Re-throw to see full stack trace
    }
  }

  // Handle connection after scanning QR code with Xaman
  async connectXamanWallet(): Promise<void> {
    this.isLoading = true;
    this.errorMessage = '';

    try {
      if (!this.payloadId) {
        throw new Error('No payload ID available. Generate a QR code first.');
      }

      // Poll the payload status
      const payloadStatus = await this.xumm.payload.get(this.payloadId);

      if (!payloadStatus) {
        throw new Error('Failed to retrieve payload status.');
      }

      // Check if the payload was signed
      if (payloadStatus.meta.signed) {
        // Extract the wallet address from the signed payload
        const walletAddress = payloadStatus.response?.account;

        if (!walletAddress) {
          throw new Error('No wallet address found in the signed payload.');
        }

        this.connectedWallet = {
          address: walletAddress
        };

        // Store the wallet in the service
        this.walletService.setWallet(this.connectedWallet);

        console.log('Connected Xaman wallet:', this.connectedWallet);
        this.snackBar.open('Successfully connected to Xaman wallet!', 'Close', { duration: 3000 });
        this.qrData = ''; // Clear QR code after connection
      } else {
        throw new Error('User did not sign the payload.');
      }
    } catch (error: any) {
      console.error('Error connecting to Xaman wallet:', error);
      let errorMessage: string;
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error as any).message;
      } else {
        errorMessage = 'An unexpected error occurred while connecting to Xaman wallet.';
      }
      this.errorMessage = errorMessage;
      this.snackBar.open(this.errorMessage, 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
    } finally {
      this.isLoading = false;
      this.cdr.detectChanges(); // Force update after connection attempt
    }
  }

  getWalletAddress(): string | null {
    return this.connectedWallet?.address || null;
  }

  getWalletSeed(): string | null {
    return this.connectedWallet?.seed || null;
  }

   // Disconnect the Xaman wallet and invalidate the payload on the server
  async disconnectWallet(): Promise<void> {
    // const confirm = confirm('Are you sure you want to disconnect your wallet?');
      // if (!confirm) return;

    this.isLoading = true; // Set loading state during disconnection
    this.errorMessage = ''; // Clear any error messages

    try {
      if (this.payloadId) {
        // Attempt to cancel or expire the payload on the server side using XummService
        await this.xummService.cancelPayload(this.payloadId).toPromise(); // Use .toPromise() or lastValueFrom for async/await
      }

      // Client-side state reset
      this.connectedWallet = null; // Clear the connected wallet
      this.qrData = ''; // Clear the QR code data
      this.payloadId = null; // Clear the payload ID
      this.walletService.setWallet(null); // Clear the wallet from the service (if using WalletService)

      this.snackBar.open('Wallet disconnected successfully.', 'Close', { duration: 3000 });
    } catch (error) {
      console.error('Error disconnecting wallet:', error);
      this.errorMessage = 'Failed to disconnect wallet. Please try again.';
      this.snackBar.open(this.errorMessage, 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
    } finally {
      this.isLoading = false; // Clear loading state
      this.cdr.detectChanges(); // Force Angular to detect changes and update the UI
    }
  }

  // Trigger both QR generation and connection attempt
  async onConnectButtonClick(): Promise<void> {
    console.log('Button clicked. Initial State:', { isLoading: this.isLoading, connectedWallet: this.connectedWallet, qrData: this.qrData });
    if (!this.qrData) {
      await this.generateQrCode();
    }
    if (this.qrData && !this.connectedWallet) {
      await this.connectXamanWallet();
    }
    console.log('After button click, State:', { isLoading: this.isLoading, connectedWallet: this.connectedWallet, qrData: this.qrData });
  }
}