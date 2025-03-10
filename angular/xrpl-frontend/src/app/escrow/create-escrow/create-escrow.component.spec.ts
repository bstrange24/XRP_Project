import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreateEscrowComponent } from './create-escrow.component';

describe('CreateEscrowComponent', () => {
  let component: CreateEscrowComponent;
  let fixture: ComponentFixture<CreateEscrowComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CreateEscrowComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreateEscrowComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
