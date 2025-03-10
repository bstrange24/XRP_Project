import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ChecksInfoComponent } from './checks-info.component';

describe('ChecksInfoComponent', () => {
  let component: ChecksInfoComponent;
  let fixture: ComponentFixture<ChecksInfoComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ChecksInfoComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ChecksInfoComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
