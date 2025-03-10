import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CashTokenCheckComponent } from './cash-token-check.component';

describe('CashTokenCheckComponent', () => {
  let component: CashTokenCheckComponent;
  let fixture: ComponentFixture<CashTokenCheckComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CashTokenCheckComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CashTokenCheckComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
