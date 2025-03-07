import { ComponentFixture, TestBed } from '@angular/core/testing';

import { BuyNftsComponent } from './buy-nfts.component';

describe('BuyNftsComponent', () => {
  let component: BuyNftsComponent;
  let fixture: ComponentFixture<BuyNftsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BuyNftsComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(BuyNftsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
