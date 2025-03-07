import { ComponentFixture, TestBed } from '@angular/core/testing';

import { MintNftsComponent } from './mint-nfts.component';

describe('MintNftsComponent', () => {
  let component: MintNftsComponent;
  let fixture: ComponentFixture<MintNftsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MintNftsComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(MintNftsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
