import { ComponentFixture, TestBed } from '@angular/core/testing';

import { EscrowInfoComponent } from './escrow-info.component';

describe('EscrowInfoComponent', () => {
  let component: EscrowInfoComponent;
  let fixture: ComponentFixture<EscrowInfoComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EscrowInfoComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(EscrowInfoComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
