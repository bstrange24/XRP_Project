import { ComponentFixture, TestBed } from '@angular/core/testing';

import { UpdateAccountConfigComponent } from './update-account-config.component';

describe('UpdateAccountConfigComponent', () => {
  let component: UpdateAccountConfigComponent;
  let fixture: ComponentFixture<UpdateAccountConfigComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UpdateAccountConfigComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(UpdateAccountConfigComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
