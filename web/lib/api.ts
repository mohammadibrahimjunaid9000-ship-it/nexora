import type { UserProfileResponse, UpdateProfileRequest, PublicUserProfile } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export class ApiError extends Error {
  status: number;
  detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    credentials: options.credentials ?? 'include',
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    let message = `API error: ${response.status}`;
    if (typeof errorData.detail === 'string') {
      message = errorData.detail;
    } else if (Array.isArray(errorData.detail) && errorData.detail.length > 0) {
      message = errorData.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ');
    } else if (typeof errorData.message === 'string') {
      message = errorData.message;
    }
    throw new ApiError(response.status, message, errorData.detail);
  }

  return response.json();
}

/**
 * Fetch authoritative profile of the currently authenticated user.
 * Relies exclusively on HttpOnly credentials.
 */
export async function getAuthenticatedProfile(): Promise<UserProfileResponse> {
  return fetchApi<UserProfileResponse>('/api/v1/users/me', {
    method: 'GET',
  });
}

/**
 * Update authenticated user's display name.
 * Anti-IDOR: Derives user identity strictly from session credentials.
 */
export async function updateAuthenticatedProfileName(
  payload: UpdateProfileRequest
): Promise<UserProfileResponse> {
  return fetchApi<UserProfileResponse>('/api/v1/users/me', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

/**
 * Fetch public profile of a user by their numeric identifier.
 * Unauthenticated endpoint; strictly validates userId > 0 and integer.
 */
export async function getPublicUserProfile(userId: number): Promise<PublicUserProfile> {
  if (typeof userId !== 'number' || !Number.isInteger(userId) || userId <= 0) {
    throw new Error('User ID must be a positive integer.');
  }
  return fetchApi<PublicUserProfile>(`/api/v1/users/${userId}`, {
    method: 'GET',
  });
}
