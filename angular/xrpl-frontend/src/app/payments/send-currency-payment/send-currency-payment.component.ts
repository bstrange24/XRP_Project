import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ValidationUtils } from '../../utlities/validation-utils';

@Component({
    selector: 'app-send-currency-payment',
    standalone: true,
    imports: [CommonModule, FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule],
    templateUrl: './send-currency-payment.component.html',
    styleUrls: ['./send-currency-payment.component.css']
})
export class SendCurrencyPaymentComponent {
    senderSeed = '';
    destinationAddress = '';
    sourceCurrency = '';
    sourceIssuer = '';
    destinationCurrency = '';
    destinationIssuer = '';
    amountToDeliver = '';
    maxToSpend = '';
    paymentResult: any | null = null;
    isLoading = false;
    errorMessage = '';

    constructor(
        private readonly snackBar: MatSnackBar,
        private readonly http: HttpClient
    ) {}

    private showError(message: string): void {
        this.snackBar.open(message, 'Close', { duration: 3000, panelClass: ['error-snackbar'] });
        this.isLoading = false;
    }

    async sendCurrencyPayment(): Promise<void> {
        this.isLoading = true;
        this.errorMessage = '';
        this.paymentResult = null;

        try {
            // Validate inputs using ValidationUtils
            if (!this.senderSeed.trim()) return this.showError('Please enter a sender wallet seed.');
            if (!ValidationUtils.isValidXrpAddress(this.destinationAddress)) return this.showError('Please enter a valid destination XRP address.');
            if (!ValidationUtils.isValidCommaSeparatedList(this.sourceCurrency)) return this.showError('Please enter a valid 3-character source currency code (e.g., USD).');
            if (!ValidationUtils.isValidXrpAddress(this.sourceIssuer)) return this.showError('Please enter a valid source issuer XRP address.');
            if (!ValidationUtils.isValidCommaSeparatedList(this.destinationCurrency)) return this.showError('Please enter a valid 3-character destination currency code (e.g., EUR).');
            if (!ValidationUtils.isValidXrpAddress(this.destinationIssuer)) return this.showError('Please enter a valid destination issuer XRP address.');
            if (!ValidationUtils.isValidNumberList(this.amountToDeliver)) return this.showError('Please enter a valid positive amount to deliver.');
            if (!ValidationUtils.isValidNumberList(this.maxToSpend)) return this.showError('Please enter a valid positive max to spend.');

            // Prepare API request parameters
            const params = new HttpParams()
                .set('sender_seed', this.senderSeed.trim())
                .set('destination_address', this.destinationAddress.trim())
                .set('source_currency', this.sourceCurrency.trim().toUpperCase())
                .set('source_issuer', this.sourceIssuer.trim())
                .set('destination_currency', this.destinationCurrency.trim().toUpperCase())
                .set('destination_issuer', this.destinationIssuer.trim())
                .set('amount_to_deliver', this.amountToDeliver.trim())
                .set('max_to_spend', this.maxToSpend.trim());

            // Send request
            const response = await firstValueFrom(this.http.get('http://127.0.0.1:8000/xrpl/send-cross-currency-payment/', { params }));
            this.paymentResult = response;
            this.isLoading = false;
            console.log('Cross-currency payment sent:', response);
        } catch (error: any) {
            console.error('Error sending cross-currency payment:', error);
            this.errorMessage = error?.message || 'An unexpected error occurred while sending the payment.';
            this.paymentResult = { status: 'error', message: this.errorMessage };
            this.showError(this.errorMessage);
        }
    }
}
