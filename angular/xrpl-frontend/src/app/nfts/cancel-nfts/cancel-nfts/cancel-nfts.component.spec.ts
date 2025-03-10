import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CancelNftsComponent } from './cancel-nfts.component';

describe('CancelNftsComponent', () => {
  let component: CancelNftsComponent;
  let fixture: ComponentFixture<CancelNftsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CancelNftsComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CancelNftsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
