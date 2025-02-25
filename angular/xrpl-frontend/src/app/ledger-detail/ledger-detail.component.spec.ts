import { ComponentFixture, TestBed } from '@angular/core/testing';

import { LedgerDetailComponent } from './ledger-detail.component';

describe('LedgerDetailComponent', () => {
  let component: LedgerDetailComponent;
  let fixture: ComponentFixture<LedgerDetailComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LedgerDetailComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(LedgerDetailComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
