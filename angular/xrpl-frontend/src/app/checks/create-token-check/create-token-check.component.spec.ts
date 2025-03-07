import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreateTokenCheckComponent } from './create-token-check.component';

describe('CreateTokenCheckComponent', () => {
  let component: CreateTokenCheckComponent;
  let fixture: ComponentFixture<CreateTokenCheckComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CreateTokenCheckComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreateTokenCheckComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
