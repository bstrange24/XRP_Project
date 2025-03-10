// src/app/services/xumm-data/xumm.service.ts
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class XummService {
  private readonly backendUrl = 'http://localhost:3000/api/xumm/payload';

  constructor(private readonly http: HttpClient) {}

  createPayload(payload: any): Observable<any> {
    const headers = new HttpHeaders({
      'X-API-Key': '93b47736-fd5d-4d16-968f-c1c565c8e54f',
      'X-API-Secret': '3a89cac1-613b-49b5-b125-1d1a8ba3b35b',
    });

    return this.http.post(this.backendUrl, payload, { headers });
  }

  cancelPayload(payloadId: string): Observable<any> {
    const headers = new HttpHeaders({
      'X-API-Key': '93b47736-fd5d-4d16-968f-c1c565c8e54f',
      'X-API-Secret': '3a89cac1-613b-49b5-b125-1d1a8ba3b35b',
    });

    return this.http.delete(`${this.backendUrl}/${payloadId}`, { headers });
  }

  getPayloadStatus(payloadId: string): Observable<any> {
    const headers = new HttpHeaders({
      'X-API-Key': '93b47736-fd5d-4d16-968f-c1c565c8e54f',
      'X-API-Secret': '3a89cac1-613b-49b5-b125-1d1a8ba3b35b',
    });

    return this.http.get(`${this.backendUrl}/${payloadId}`, { headers });
  }
}