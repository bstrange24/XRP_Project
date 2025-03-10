import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SendCurrencyPaymentComponent } from './send-currency-payment.component';

describe('SendCurrencyPaymentComponent', () => {
  let component: SendCurrencyPaymentComponent;
  let fixture: ComponentFixture<SendCurrencyPaymentComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SendCurrencyPaymentComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SendCurrencyPaymentComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
