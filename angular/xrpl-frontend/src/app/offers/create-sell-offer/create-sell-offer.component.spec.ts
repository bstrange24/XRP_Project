import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreateSellOfferComponent } from './create-sell-offer.component';

describe('CreateSellOfferComponent', () => {
  let component: CreateSellOfferComponent;
  let fixture: ComponentFixture<CreateSellOfferComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CreateSellOfferComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreateSellOfferComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
