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

export interface PublicUserProfile {
  id: number;
  name: string;
  role: 'learner' | 'creator' | 'admin';
}

// Stage 8 Course Catalog Types
export interface CourseListItem {
  id: number;
  title: string;
  description: string;
  instructor: string;
  category: string;
  level: string;
  duration: string;
  thumbnail?: string | null;
  total_lessons: number;
  rating: number;
  price: number;
  points_price: number;
  created_at?: string | null;
}

export interface CourseDetail {
  id: number;
  title: string;
  description: string;
  instructor: string;
  category: string;
  level: string;
  duration: string;
  thumbnail?: string | null;
  total_lessons: number;
  rating: number;
  price: number;
  points_price: number;
  created_by?: number | null;
  created_at?: string | null;
}

export interface CourseListResponse {
  courses: CourseListItem[];
  total: number;
}

export interface CourseFilterParams {
  search?: string;
  category?: string;
  level?: string;
}
