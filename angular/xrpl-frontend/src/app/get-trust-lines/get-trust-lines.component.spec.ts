import { ComponentFixture, TestBed } from '@angular/core/testing';

import { GetTrustLinesComponent } from './get-trust-lines.component';

describe('GetTrustLinesComponent', () => {
  let component: GetTrustLinesComponent;
  let fixture: ComponentFixture<GetTrustLinesComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GetTrustLinesComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(GetTrustLinesComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
