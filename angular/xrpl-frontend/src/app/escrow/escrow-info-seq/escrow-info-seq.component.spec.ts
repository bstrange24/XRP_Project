import { ComponentFixture, TestBed } from '@angular/core/testing';

import { EscrowInfoSeqComponent } from './escrow-info-seq.component';

describe('EscrowInfoSeqComponent', () => {
  let component: EscrowInfoSeqComponent;
  let fixture: ComponentFixture<EscrowInfoSeqComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EscrowInfoSeqComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(EscrowInfoSeqComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
