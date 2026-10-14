// Shared TypeScript type definitions for Nexora
export interface ApiResponse<T = unknown> {
  status: string;
  data?: T;
  message?: string;
  error?: string;
}

export interface HealthCheckResponse {
  status: string;
  service: string;
  version: string;
}

export interface UserProfileResponse {
  id: number;
  name: string;
  email: string;
  role: string | null;
  points: number;
  joined_at: string | null;
}

export interface UpdateProfileRequest {
  name: string;
}
