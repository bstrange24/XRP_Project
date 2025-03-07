import { ComponentFixture, TestBed } from '@angular/core/testing';

import { GetAccountConfigComponent } from './get-account-config.component';

describe('GetAccountConfigComponent', () => {
  let component: GetAccountConfigComponent;
  let fixture: ComponentFixture<GetAccountConfigComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GetAccountConfigComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(GetAccountConfigComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
