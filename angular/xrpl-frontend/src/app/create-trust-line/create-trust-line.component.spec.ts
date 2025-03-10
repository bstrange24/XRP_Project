import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreateTrustLineComponent } from './create-trust-line.component';

describe('CreateTrustLineComponent', () => {
  let component: CreateTrustLineComponent;
  let fixture: ComponentFixture<CreateTrustLineComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CreateTrustLineComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreateTrustLineComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
