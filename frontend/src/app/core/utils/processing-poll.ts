import { HttpErrorResponse, HttpResponse } from '@angular/common/http';
import { EMPTY, Observable, throwError, timer } from 'rxjs';
import { expand, filter, map, switchMap, take } from 'rxjs/operators';

import { ProcessingStatusResponse } from '../models/api.models';

const DEFAULT_INTERVAL_MS = 5000;
const DEFAULT_MAX_MS = 120_000;

export const DEFAULT_EMBEDDING_PROCESSING_MESSAGE =
  'Processando embeddings desta conversa grande, isso pode levar alguns minutos...';

export const DEFAULT_TRANSCRIPTION_PROCESSING_MESSAGE =
  'Transcrevendo áudio, isso pode levar alguns instantes...';

export class ProcessingPollTimeoutError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ProcessingPollTimeoutError';
  }
}

export function pollHttpPost<T>(
  request: () => Observable<HttpResponse<T | ProcessingStatusResponse>>,
  onProcessing?: (status: ProcessingStatusResponse) => void,
  intervalMs = DEFAULT_INTERVAL_MS,
  maxMs = DEFAULT_MAX_MS,
): Observable<T> {
  const maxAttempts = Math.ceil(maxMs / intervalMs);
  let attempt = 0;

  return request().pipe(
    expand((response) => {
      if (response.status === 200) {
        return EMPTY;
      }
      if (response.status === 202) {
        attempt += 1;
        const body = (response.body ?? {
          status: 'PROCESSING',
          message: DEFAULT_EMBEDDING_PROCESSING_MESSAGE,
        }) as ProcessingStatusResponse;
        onProcessing?.(body);
        if (attempt >= maxAttempts) {
          return throwError(
            () =>
              new ProcessingPollTimeoutError(
                'O processamento dos embeddings demorou mais que o esperado. Tente novamente em alguns minutos.',
              ),
          );
        }
        return timer(intervalMs).pipe(switchMap(() => request()));
      }
      return throwError(
        () =>
          new HttpErrorResponse({
            status: response.status,
            statusText: response.statusText,
            error: response.body,
          }),
      );
    }),
    filter((response): response is HttpResponse<T> => response.status === 200),
    map((response) => {
      if (response.body == null) {
        throw new HttpErrorResponse({ status: 500, statusText: 'Resposta vazia do servidor.' });
      }
      return response.body;
    }),
    take(1),
  );
}

export function pollHttpGet<T>(
  request: () => Observable<T>,
  isDone: (body: T) => boolean,
  onProcessing?: (body: T) => void,
  intervalMs = DEFAULT_INTERVAL_MS,
  maxMs = DEFAULT_MAX_MS,
): Observable<T> {
  const maxAttempts = Math.ceil(maxMs / intervalMs);
  let attempt = 0;

  return request().pipe(
    expand((body) => {
      if (isDone(body)) {
        return EMPTY;
      }
      attempt += 1;
      onProcessing?.(body);
      if (attempt >= maxAttempts) {
        return throwError(
          () =>
            new ProcessingPollTimeoutError(
              'A transcrição demorou mais que o esperado. Tente consultar o status novamente em alguns minutos.',
            ),
        );
      }
      return timer(intervalMs).pipe(switchMap(() => request()));
    }),
    filter((body) => isDone(body)),
    take(1),
  );
}
