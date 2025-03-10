import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreateBuyOfferComponent } from './create-buy-offer.component';

describe('CreateBuyOfferComponent', () => {
  let component: CreateBuyOfferComponent;
  let fixture: ComponentFixture<CreateBuyOfferComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CreateBuyOfferComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreateBuyOfferComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
