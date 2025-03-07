import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SetDidComponent } from './set-did.component';

describe('SetDidComponent', () => {
  let component: SetDidComponent;
  let fixture: ComponentFixture<SetDidComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SetDidComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SetDidComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
