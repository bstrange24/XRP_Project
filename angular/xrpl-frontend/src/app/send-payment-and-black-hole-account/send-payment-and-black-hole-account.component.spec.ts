import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SendPaymentAndBlackHoleAccountComponent } from './send-payment-and-black-hole-account.component';

describe('SendPaymentAndBlackHoleAccountComponent', () => {
  let component: SendPaymentAndBlackHoleAccountComponent;
  let fixture: ComponentFixture<SendPaymentAndBlackHoleAccountComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SendPaymentAndBlackHoleAccountComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SendPaymentAndBlackHoleAccountComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
