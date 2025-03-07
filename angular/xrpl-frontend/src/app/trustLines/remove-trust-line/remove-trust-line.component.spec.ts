import { ComponentFixture, TestBed } from '@angular/core/testing';

import { RemoveTrustLineComponent } from './remove-trust-line.component';

describe('RemoveTrustLineComponent', () => {
  let component: RemoveTrustLineComponent;
  let fixture: ComponentFixture<RemoveTrustLineComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RemoveTrustLineComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(RemoveTrustLineComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
