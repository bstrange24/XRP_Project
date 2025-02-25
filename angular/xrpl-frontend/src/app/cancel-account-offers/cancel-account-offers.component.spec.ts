import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CancelAccountOffersComponent } from './cancel-account-offers.component';

describe('CancelAccountOffersComponent', () => {
  let component: CancelAccountOffersComponent;
  let fixture: ComponentFixture<CancelAccountOffersComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CancelAccountOffersComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CancelAccountOffersComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
