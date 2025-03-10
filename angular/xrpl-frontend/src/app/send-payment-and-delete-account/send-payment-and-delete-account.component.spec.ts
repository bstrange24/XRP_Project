import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SendPaymentAndDeleteAccountComponent } from './send-payment-and-delete-account.component';

describe('SendPaymentAndDeleteAccountComponent', () => {
  let component: SendPaymentAndDeleteAccountComponent;
  let fixture: ComponentFixture<SendPaymentAndDeleteAccountComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SendPaymentAndDeleteAccountComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SendPaymentAndDeleteAccountComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
