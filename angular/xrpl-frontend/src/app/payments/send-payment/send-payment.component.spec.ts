import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SendPaymentComponent } from './send-payment.component';

describe('SendPaymentComponent', () => {
  let component: SendPaymentComponent;
  let fixture: ComponentFixture<SendPaymentComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SendPaymentComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SendPaymentComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
