import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async'; // Add this


bootstrapApplication(AppComponent, appConfig)
  .catch((err) => console.error(err));
