import { ApplicationConfig } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { WalletService } from './services/wallet-services/wallet.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideHttpClient(),
    WalletService
  ],
};
