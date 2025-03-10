import { ComponentFixture, TestBed } from '@angular/core/testing';

import { GetNftsComponent } from './get-nfts.component';

describe('GetNftsComponent', () => {
  let component: GetNftsComponent;
  let fixture: ComponentFixture<GetNftsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GetNftsComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(GetNftsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
