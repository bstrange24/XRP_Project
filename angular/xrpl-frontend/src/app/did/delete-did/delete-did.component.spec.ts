import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DeleteDidComponent } from './delete-did.component';

describe('DeleteDidComponent', () => {
  let component: DeleteDidComponent;
  let fixture: ComponentFixture<DeleteDidComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DeleteDidComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(DeleteDidComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
