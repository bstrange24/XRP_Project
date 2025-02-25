import { ComponentFixture, TestBed } from '@angular/core/testing';

import { GetAccountOffersComponent } from './get-account-offers.component';

describe('GetAccountOffersComponent', () => {
  let component: GetAccountOffersComponent;
  let fixture: ComponentFixture<GetAccountOffersComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GetAccountOffersComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(GetAccountOffersComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
