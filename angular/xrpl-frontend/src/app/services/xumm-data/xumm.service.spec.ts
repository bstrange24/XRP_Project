import { TestBed } from '@angular/core/testing';

import { XummService } from './xumm.service';

describe('XummService', () => {
  let service: XummService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(XummService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
