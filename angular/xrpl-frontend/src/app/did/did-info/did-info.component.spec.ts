import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DidInfoComponent } from './did-info.component';

describe('DidInfoComponent', () => {
  let component: DidInfoComponent;
  let fixture: ComponentFixture<DidInfoComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DidInfoComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(DidInfoComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
