import { ComponentFixture, TestBed } from '@angular/core/testing';

import { GetBookOffersComponent } from './get-book-offers.component';

describe('GetBookOffersComponent', () => {
  let component: GetBookOffersComponent;
  let fixture: ComponentFixture<GetBookOffersComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GetBookOffersComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(GetBookOffersComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
