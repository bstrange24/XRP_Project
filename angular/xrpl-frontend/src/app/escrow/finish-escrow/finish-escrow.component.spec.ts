import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FinishEscrowComponent } from './finish-escrow.component';

describe('FinishEscrowComponent', () => {
  let component: FinishEscrowComponent;
  let fixture: ComponentFixture<FinishEscrowComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FinishEscrowComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(FinishEscrowComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
