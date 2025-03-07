import { ComponentFixture, TestBed } from '@angular/core/testing';

import { BurnNftsComponent } from './burn-nfts.component';

describe('BurnNftsComponent', () => {
  let component: BurnNftsComponent;
  let fixture: ComponentFixture<BurnNftsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BurnNftsComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(BurnNftsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
