import { TestBed } from '@angular/core/testing';

import { XrplService } from './xrpl.service';

describe('XrplService', () => {
  let service: XrplService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(XrplService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
