import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CancelCheckComponent } from './cancel-check.component';

describe('CancelCheckComponent', () => {
  let component: CancelCheckComponent;
  let fixture: ComponentFixture<CancelCheckComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CancelCheckComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CancelCheckComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
