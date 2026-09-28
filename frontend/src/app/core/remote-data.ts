import { HttpErrorResponse } from '@angular/common/http';
import { TimeoutError } from 'rxjs';

/** State of data loaded from the API, as displayed by the UI. */
export type RemoteData<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: string };

export const IDLE = { status: 'idle' } as const;
export const LOADING = { status: 'loading' } as const;

export function success<T>(data: T): RemoteData<T> {
  return { status: 'success', data };
}

export function failure<T>(error: unknown): RemoteData<T> {
  return { status: 'error', error: errorMessage(error) };
}

/** User-facing message for an HTTP / network error. */
export function errorMessage(error: unknown): string {
  if (error instanceof TimeoutError) {
    return 'Le serveur a mis trop de temps à répondre.';
  }
  if (error instanceof HttpErrorResponse) {
    if (error.status === 0) {
      return "Impossible de joindre l'API : vérifiez votre connexion et que le backend est démarré.";
    }
    const detail = typeof error.error?.detail === 'string' ? error.error.detail : null;
    switch (error.status) {
      case 429:
        return `Trop de requêtes, réessayez dans un instant.${detail ? ` (${detail})` : ''}`;
      case 504:
        return 'Un service externe a mis trop de temps à répondre.';
      default:
        return detail ? `Erreur ${error.status} : ${detail}` : `Erreur ${error.status} du serveur.`;
    }
  }
  return 'Erreur inattendue.';
}
