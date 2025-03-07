import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient } from '@angular/common/http';
import { XrplService } from '../../services/xrpl-data/xrpl.service';
import { SharedDataService } from '../../services/shared-data/shared-data.service';

@Component({
  selector: 'app-create-account',
  standalone: true,
  imports: [CommonModule, FormsModule, MatCardModule, MatButtonModule],
  templateUrl: './create-account.component.html',
  styleUrls: ['./create-account.component.css']
})
export class CreateAccountComponent {
  newAccount: any | null = null;
  isLoading: boolean = false;
  errorMessage: string = '';

  constructor(
    private readonly xrplService: XrplService,
    private readonly snackBar: MatSnackBar,
    private readonly http: HttpClient,
    private readonly sharedDataService: SharedDataService // Inject SharedDataService
  ) {
    // Subscribe to newAccount from the service
    this.sharedDataService.newAccount$.subscribe(account => {
      this.newAccount = account;
      if (!this.newAccount) {
        this.newAccount = { status: 'error', message: 'No account creation data available.' };
        this.errorMessage = this.newAccount.message;
        this.snackBar.open(this.errorMessage, 'Close', {
          duration: 3000,
          panelClass: ['error-snackbar']
        });
      }
    });
  }
}