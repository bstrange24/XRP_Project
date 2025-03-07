import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CashXrpCheckComponent } from './cash-xrp-check.component';

describe('CashXrpCheckComponent', () => {
  let component: CashXrpCheckComponent;
  let fixture: ComponentFixture<CashXrpCheckComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CashXrpCheckComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CashXrpCheckComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
