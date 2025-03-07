import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreateXrpCheckComponent } from './create-xrp-check.component';

describe('CreateXrpCheckComponent', () => {
  let component: CreateXrpCheckComponent;
  let fixture: ComponentFixture<CreateXrpCheckComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CreateXrpCheckComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreateXrpCheckComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
