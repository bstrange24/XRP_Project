import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatSnackBarModule } from '@angular/material/snack-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { NgxQrcodeStylingModule } from 'ngx-qrcode-styling';
import { XummSdk } from 'xumm-sdk';
import { HttpClient } from '@angular/common/http';
import { lastValueFrom } from 'rxjs';
import { XummService } from '../services/xumm-data/xumm.service';
import { WalletService } from '../services/wallet-services/wallet.service';

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
  private payloadExpiration: number | null = null; // Store expiration time in seconds

  // Storage key for wallet data
  private readonly WALLET_STORAGE_KEY = 'xamanWallet';

  // Flag to prevent multiple simultaneous generateQrCode calls
  private isGenerating: boolean = false;

  // Development flag to simulate signing (for testing without Xaman)
  private readonly IS_DEVELOPMENT = true; // Set to false for production

  // Initialize the Xumm SDK with your API credentials
  private readonly xumm = new XummSdk('93b47736-fd5d-4d16-968f-c1c565c8e54f', '3a89cac1-613b-49b5-b125-1d1a8ba3b35b');

  constructor(
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient,
    private readonly xummService: XummService,
    private cdr: ChangeDetectorRef,
    private walletService: WalletService // Inject WalletService if used
  ) {}

  ngOnInit(): void {
    const storedWallet = sessionStorage.getItem(this.WALLET_STORAGE_KEY);
    if (storedWallet) {
      this.connectedWallet = JSON.parse(storedWallet);
      this.walletService.setWallet(this.connectedWallet); // Update WalletService if used
      console.log('Restored wallet from sessionStorage:', this.connectedWallet);
      
      // Clear payloadId and qrData on init, but only if not actively connecting
      if (!this.isLoading && !this.qrData) {
        this.payloadId = null;
        this.qrData = '';
        this.payloadExpiration = null;
        console.log('Cleared payloadId, qrData, and payloadExpiration on init to prevent using expired payloads.');
      }
    }
  }

  getWalletAddress(): string | null {
    return this.connectedWallet?.address || null;
  }

  // Generate a QR code for Xaman wallet connection with adjusted expiration
  private async generateQrCode(): Promise<void> {
    if (this.isGenerating || this.isLoading || this.connectedWallet) {
      console.warn('generateQrCode already in progress or wallet connected, skipping...');
      return;
    }
  
    this.isGenerating = true;
    this.isLoading = true;
    this.errorMessage = '';
    this.cdr.detectChanges();
    console.log('Starting QR code generation... State:', { isLoading: this.isLoading, connectedWallet: this.connectedWallet, qrData: this.qrData, isGenerating: this.isGenerating });
  
    try {
      const payload = {
        txjson: { TransactionType: 'SignIn' as const },
        options: { expire: 2 } // 2 minutes = 120 seconds
      };
      console.log('Payload being sent:', payload);
      const response = await lastValueFrom(this.xummService.createPayload(payload));
      console.log('Full payload response:', JSON.stringify(response, null, 2));
  
      const expireTimeMinutes = response.payload?.expire || response.meta?.expire || 2;
      const expireTimeSeconds = typeof expireTimeMinutes === 'number' ? expireTimeMinutes * 60 : 120;
      this.payloadExpiration = expireTimeSeconds;
      console.log('Payload expiration time:', this.payloadExpiration, 'seconds');
  
      // Use the Xumm sign URL instead of custom deep link
      this.qrData = `https://xumm.app/sign/${response.uuid}`;
      this.payloadId = response.uuid;
      console.log('Payload ID set:', this.payloadId);
      console.log('QR code data set:', this.qrData);
  
      this.isLoading = false;
      this.isGenerating = false;
      this.snackBar.open(`Scan the QR code with Xaman to connect. Expires in ${this.payloadExpiration} seconds.`, 'Close', { duration: 5000 });
      this.cdr.detectChanges();
      console.log('After update, State (post QR code):', { isLoading: this.isLoading, connectedWallet: this.connectedWallet, qrData: this.qrData, isGenerating: this.isGenerating });
  
      if (!this.connectedWallet && this.payloadId) {
        this.connectXamanWallet();
      }
    } catch (error) {
      console.error('Error creating payload:', error);
      console.error('Error generating QR code:', JSON.stringify(error, null, 2));
      let errorMessage: string;
  
      if (typeof error === 'object' && error !== null) {
        if ('status' in error && error.status === 404) {
          errorMessage = 'Proxy server endpoint not found. Ensure the server is running on localhost:3000 and the endpoint /api/xumm/payload is defined.';
        } else if ('status' in error && error.status === 401) {
          errorMessage = 'Invalid Xumm API credentials. Please check your API key and secret.';
        } else if ('status' in error && error.status === 403) {
          errorMessage = 'Access denied. Check Xumm API permissions.';
        } else if (
          'status' in error && error.status === 400 &&
          'error' in error && error.error !== null && typeof error.error === 'object' &&
          'message' in error.error && typeof error.error.message === 'string' && error.error.message.includes('expire')
        ) {
          errorMessage = 'Invalid expiration time requested. Using default expiration (120 seconds).';
          const defaultPayload = { txjson: { TransactionType: 'SignIn' as const }, options: { expire: 2 } };
          try {
            const defaultResponse = await lastValueFrom(this.xummService.createPayload(defaultPayload));
            console.log('Fallback payload created successfully:', defaultResponse);
            const expireTimeMinutes = defaultResponse.payload?.expire || defaultResponse.meta?.expire || 2;
            this.payloadExpiration = typeof expireTimeMinutes === 'number' ? expireTimeMinutes * 60 : 120;
            this.qrData = `https://xumm.app/sign/${defaultResponse.uuid}`;
            this.payloadId = defaultResponse.uuid;
            console.log('Fallback QR code data set:', this.qrData);
            this.snackBar.open(`Scan the QR code with Xaman to connect. Expires in ${this.payloadExpiration} seconds.`, 'Close', { duration: 5000 });
            this.cdr.detectChanges();
            if (!this.connectedWallet && this.payloadId) {
              this.connectXamanWallet();
            }
          } catch (fallbackError) {
            this.handlePayloadError(fallbackError, 'Failed to generate QR code with fallback. Check Xumm API credentials, network, or proxy.');
          }
          return;
        } else if ('status' in error && error.status === 500) {
          errorMessage = 'Xumm API or proxy server error. Check network or server status.';
        } else if ('name' in error && error.name === 'TimeoutError') {
          errorMessage = 'Network timeout. Check your connection to the proxy server.';
        } else if ('name' in error && error.name === 'TypeError' && 'message' in error && typeof error.message === 'string' && error.message.includes('Network request failed')) {
          errorMessage = 'Network error. Ensure the proxy server is running on localhost:3000.';
        } else {
          errorMessage = 'Failed to generate QR code for wallet connection. Check Xumm API credentials, network, or proxy.';
        }
      } else {
        errorMessage = 'An unexpected error occurred while generating the QR code.';
      }
  
      this.handlePayloadError(error, errorMessage);
    } finally {
      this.isLoading = false;
      this.isGenerating = false;
      this.cdr.detectChanges();
    }
  }

  private handlePayloadError(error: any, defaultMessage: string): void {
    let errorMessage: string = defaultMessage;
    if (error.status === 400 && error.error?.message?.includes('expire')) {
      errorMessage += ' Xumm rejected the expiration time. Using default expiration.';
    }
    this.errorMessage = errorMessage;
    this.snackBar.open(this.errorMessage, 'Close', { duration: 5000, panelClass: ['error-snackbar'] });
    this.cdr.detectChanges();
    this.cdr.markForCheck(); // Ensure change detection triggers for the error
    throw error;
  }

  // Handle connection after scanning QR code with Xaman, with extended delays and retries
  async connectXamanWallet(): Promise<void> {
    this.isLoading = true;
    this.errorMessage = '';
  
    try {
      if (!this.payloadId) {
        throw new Error('No payload ID available. Generate a QR code first.');
      }
  
      await new Promise(resolve => setTimeout(resolve, 500)); // Wait 500ms for payload to settle
      const startTime = Date.now();
      const maxWaitTime = (this.payloadExpiration ?? 120) * 1000;
      console.log(`Starting payload status check loop. Payload ID: ${this.payloadId}, Max wait time: ${maxWaitTime}ms`);
  
      while (Date.now() - startTime < maxWaitTime) {
        console.log(`Checking payload status at ${Date.now() - startTime}ms elapsed`);
        const checkStart = Date.now();
        const payloadStatus = await lastValueFrom(this.xummService.getPayloadStatus(this.payloadId));
        console.log(`Status check took ${Date.now() - checkStart}ms`);
        // console.log('Payload status:', JSON.stringify(payloadStatus, null, 2));
  
        if (!payloadStatus) {
          throw new Error('Failed to retrieve payload status or payload not found.');
        }
  
        if (payloadStatus.meta.signed) {
          const walletAddress = payloadStatus.response?.account;
          if (!walletAddress) {
            throw new Error('No wallet address found in the signed payload.');
          }
  
          this.connectedWallet = { address: walletAddress };
          sessionStorage.setItem(this.WALLET_STORAGE_KEY, JSON.stringify(this.connectedWallet));
          this.walletService.setWallet(this.connectedWallet);
          console.log('Connected Xaman wallet:', this.connectedWallet);
          this.snackBar.open('Successfully connected to Xaman wallet!', 'Close', { duration: 3000 });
          this.qrData = '';
          break;
        }
  
        // Only check meta.expired, ignore canBeSigned since it’s not in the response
        const isExpired = payloadStatus.meta.expired;
        console.log(`Payload expired: ${isExpired}`);
        if (isExpired) {
          throw new Error('The payload has expired. Please generate a new QR code and reconnect.');
        }
  
        console.log('Payload not signed yet, waiting 1 second...');
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
  
      if (!this.connectedWallet) {
        if (this.IS_DEVELOPMENT) {
          console.log('Development mode: Simulating wallet connection...');
          this.connectedWallet = { address: 'rExampleAddress1234567890' };
          sessionStorage.setItem(this.WALLET_STORAGE_KEY, JSON.stringify(this.connectedWallet));
          this.walletService.setWallet(this.connectedWallet);
          this.snackBar.open('Wallet connected (simulated for development)', 'Close', { duration: 3000 });
          this.qrData = '';
        } else {
          throw new Error('User did not sign the payload within the time limit. Please try again.');
        }
      }
    } catch (error: any) {
      console.error('Error connecting to Xaman wallet:', error);
      let errorMessage: string;
      if (error instanceof Error) {
        if (error.message.includes('404') || error.message.includes('not found')) {
          errorMessage = 'The payload has expired or is not found. Please generate a new QR code and reconnect.';
          this.qrData = '';
          this.payloadId = null;
          this.payloadExpiration = null;
          sessionStorage.removeItem(this.WALLET_STORAGE_KEY);
          this.walletService.setWallet(null);
        } else if (error.message.includes('User did not sign')) {
          errorMessage = error.message;
        } else {
          errorMessage = error.message;
        }
      } else if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = (error as any).message || 'An unexpected error occurred';
      } else {
        errorMessage = 'An unexpected error occurred while connecting to Xaman wallet.';
      }
      this.errorMessage = errorMessage;
      this.snackBar.open(this.errorMessage, 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.cdr.detectChanges();
    } finally {
      this.isLoading = false;
      this.cdr.detectChanges();
    }
  }

  // Disconnect the Xaman wallet and invalidate the payload on the server
  async disconnectWallet(): Promise<void> {
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
      this.payloadExpiration = null; // Clear expiration
      sessionStorage.removeItem(this.WALLET_STORAGE_KEY); // Clear the wallet from sessionStorage
      this.walletService.setWallet(null); // Clear the wallet from the service (if using WalletService)

      this.snackBar.open('Wallet disconnected successfully.', 'Close', { duration: 3000 });
      this.cdr.detectChanges(); // Force update after disconnection
      this.cdr.markForCheck(); // Ensure change detection triggers for the state
    } catch (error) {
      console.error('Error disconnecting wallet:', error);
      this.errorMessage = 'Failed to disconnect wallet. Please try again.';
      this.snackBar.open(this.errorMessage, 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
      this.cdr.detectChanges(); // Force update after error
      this.cdr.markForCheck(); // Ensure change detection triggers for the error
    } finally {
      this.isLoading = false; // Clear loading state
      this.cdr.detectChanges(); // Force Angular to detect changes and update the UI
      this.cdr.markForCheck(); // Ensure change detection triggers for the state
    }
  }

  // Trigger both QR generation and connection attempt
  async onConnectButtonClick(): Promise<void> {
    console.log('Button clicked. Initial State:', { isLoading: this.isLoading, connectedWallet: this.connectedWallet, qrData: this.qrData, isGenerating: this.isGenerating });
    if (!this.qrData && !this.isGenerating) {
      await this.generateQrCode();
    }
    // No need to call connectXamanWallet here; it’s already triggered in generateQrCode
    console.log('After button click, State:', { isLoading: this.isLoading, connectedWallet: this.connectedWallet, qrData: this.qrData, isGenerating: this.isGenerating });
  }
}