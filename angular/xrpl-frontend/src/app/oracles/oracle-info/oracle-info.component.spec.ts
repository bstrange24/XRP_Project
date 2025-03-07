import { ComponentFixture, TestBed } from '@angular/core/testing';

import { OracleInfoComponent } from './oracle-info.component';

describe('OracleInfoComponent', () => {
  let component: OracleInfoComponent;
  let fixture: ComponentFixture<OracleInfoComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OracleInfoComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(OracleInfoComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
