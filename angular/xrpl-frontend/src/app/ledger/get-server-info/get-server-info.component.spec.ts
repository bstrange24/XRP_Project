import { ComponentFixture, TestBed } from '@angular/core/testing';

import { GetServerInfoComponent } from './get-server-info.component';

describe('GetServerInfoComponent', () => {
  let component: GetServerInfoComponent;
  let fixture: ComponentFixture<GetServerInfoComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GetServerInfoComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(GetServerInfoComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
