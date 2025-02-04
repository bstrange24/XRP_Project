import { Component } from '@angular/core';
import { AccountInfoComponent } from './account-info/account-info.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [AccountInfoComponent],
  template: `<app-account-info></app-account-info>`,
})
export class AppComponent {}
