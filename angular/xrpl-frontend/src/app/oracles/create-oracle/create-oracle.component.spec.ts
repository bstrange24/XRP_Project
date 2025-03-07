import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreateOracleComponent } from './create-oracle.component';

describe('CreateOracleComponent', () => {
  let component: CreateOracleComponent;
  let fixture: ComponentFixture<CreateOracleComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CreateOracleComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreateOracleComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
