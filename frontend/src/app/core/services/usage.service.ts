import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { UsageSummary } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class UsageService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/usage`;

  getSummary(): Observable<UsageSummary> {
    return this.http.get<UsageSummary>(this.url);
  }
}
