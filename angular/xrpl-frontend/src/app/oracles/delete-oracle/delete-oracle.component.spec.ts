import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DeleteOracleComponent } from './delete-oracle.component';

describe('DeleteOracleComponent', () => {
  let component: DeleteOracleComponent;
  let fixture: ComponentFixture<DeleteOracleComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DeleteOracleComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(DeleteOracleComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
