'use client';

import React, { use, useEffect, useState, useCallback, Suspense } from 'react';
import Link from 'next/link';
import type { CourseDetail, EnrollmentRecord, LessonItem } from '@/lib/types';
import {
  ApiError,
  getCourseById,
  getEnrollmentStatus,
  enrollInCourse,
  getCourseLessons,
} from '@/lib/api';
import {
  parseCourseId,
  formatCoursePrice,
  formatPointsPrice,
  getLevelBadgeStyle,
} from '@/lib/course-utils';


interface PageProps {
  params: Promise<{ courseId: string }>;
}

type ViewState =
  | { type: 'loading' }
  | { type: 'invalid_id' }
  | { type: 'not_found' }
  | { type: 'service_unavailable' }
  | { type: 'network_error'; message: string }
  | { type: 'success'; course: CourseDetail };

type EnrollmentState =
  | { type: 'checking' }
  | { type: 'not_enrolled' }
  | { type: 'enrolling' }
  | { type: 'enrolled'; enrollment?: EnrollmentRecord | null; justEnrolled?: boolean }
  | { type: 'unauthenticated' }
  | { type: 'error'; message: string };

type LessonsState =
  | { type: 'loading' }
  | { type: 'error'; message: string }
  | { type: 'loaded'; lessons: LessonItem[]; total: number };

function CourseDetailContent({ params }: PageProps) {
  const resolvedParams = use(params);
  const rawCourseId = resolvedParams?.courseId;

  const validCourseId = parseCourseId(rawCourseId);

  const [viewState, setViewState] = useState<ViewState>(() =>
    validCourseId === null ? { type: 'invalid_id' } : { type: 'loading' }
  );
  const [enrollmentState, setEnrollmentState] = useState<EnrollmentState>({ type: 'checking' });
  const [lessonsState, setLessonsState] = useState<LessonsState>({ type: 'loading' });
  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const [isRetryingLessons, setIsRetryingLessons] = useState<boolean>(false);


  // Fetch course details & check initial enrollment status
  useEffect(() => {
    if (validCourseId === null) return;

    let isMounted = true;

    getCourseById(validCourseId)
      .then((data) => {
        if (isMounted) {
          setViewState({ type: 'success', course: data });
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          if (err instanceof ApiError) {
            if (err.status === 404) {
              setViewState({ type: 'not_found' });
            } else if (err.status === 503) {
              setViewState({ type: 'service_unavailable' });
            } else {
              setViewState({
                type: 'network_error',
                message: err.message || 'Unable to load course.',
              });
            }
          } else if (err instanceof Error) {
            setViewState({
              type: 'network_error',
              message: err.message || 'Unable to connect to server.',
            });
          } else {
            setViewState({
              type: 'network_error',
              message: 'An unexpected error occurred.',
            });
          }
        }
      });

    getEnrollmentStatus(validCourseId)
      .then((statusRes) => {
        if (isMounted) {
          if (statusRes.is_enrolled) {
            setEnrollmentState({ type: 'enrolled', enrollment: statusRes.enrollment });
          } else {
            setEnrollmentState({ type: 'not_enrolled' });
          }
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          if (err instanceof ApiError) {
            if (err.status === 401) {
              setEnrollmentState({ type: 'unauthenticated' });
            } else if (err.status === 403) {
              setEnrollmentState({
                type: 'error',
                message: 'Only learner accounts are eligible to enroll in courses.',
              });
            } else {
              setEnrollmentState({
                type: 'error',
                message: err.message || 'Unable to verify enrollment status.',
              });
            }
          } else {
            setEnrollmentState({
              type: 'error',
              message: 'Unable to verify enrollment status.',
            });
          }
        }
      });

    getCourseLessons(validCourseId)
      .then((lessonsRes) => {
        if (isMounted) {
          setLessonsState({
            type: 'loaded',
            lessons: lessonsRes.lessons || [],
            total: lessonsRes.total ?? lessonsRes.lessons?.length ?? 0,
          });
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          const msg = err instanceof Error ? err.message : 'Unable to load course lessons.';
          setLessonsState({ type: 'error', message: msg });
        }
      });

    return () => {
      isMounted = false;
    };
  }, [validCourseId]);


  // Handle enrollment action
  const handleEnroll = async () => {
    if (
      validCourseId === null ||
      enrollmentState.type === 'enrolling' ||
      enrollmentState.type === 'enrolled'
    ) {
      return;
    }

    setEnrollmentState({ type: 'enrolling' });

    try {
      const newEnrollment = await enrollInCourse(validCourseId);
      setEnrollmentState({
        type: 'enrolled',
        enrollment: newEnrollment,
        justEnrolled: true,
      });
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          // Already enrolled
          setEnrollmentState({ type: 'enrolled' });
        } else if (err.status === 401) {
          setEnrollmentState({ type: 'unauthenticated' });
        } else if (err.status === 403) {
          setEnrollmentState({
            type: 'error',
            message: 'Learner privileges required. Creator or admin accounts cannot enroll as students.',
          });
        } else {
          setEnrollmentState({
            type: 'error',
            message: err.message || 'Enrollment request failed. Please try again.',
          });
        }
      } else if (err instanceof Error) {
        setEnrollmentState({
          type: 'error',
          message: err.message || 'Network error during enrollment.',
        });
      } else {
        setEnrollmentState({
          type: 'error',
          message: 'An unexpected error occurred during enrollment.',
        });
      }
    }
  };

  const handleRetryCourse = useCallback(async () => {
    if (validCourseId === null || isRetrying) return;
    setIsRetrying(true);

    try {
      const data = await getCourseById(validCourseId);
      setViewState({ type: 'success', course: data });
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setViewState({ type: 'not_found' });
        } else if (err.status === 503) {
          setViewState({ type: 'service_unavailable' });
        } else {
          setViewState({
            type: 'network_error',
            message: err.message || 'Unable to load course.',
          });
        }
      } else if (err instanceof Error) {
        setViewState({
          type: 'network_error',
          message: err.message || 'Unable to connect to server.',
        });
      } else {
        setViewState({
          type: 'network_error',
          message: 'An unexpected error occurred.',
        });
      }
    } finally {
      setIsRetrying(false);
    }
  }, [validCourseId, isRetrying]);

  const handleRetryLessons = useCallback(async () => {
    if (validCourseId === null || isRetryingLessons) return;
    setIsRetryingLessons(true);
    setLessonsState({ type: 'loading' });
    try {
      const data = await getCourseLessons(validCourseId);
      setLessonsState({
        type: 'loaded',
        lessons: data.lessons || [],
        total: data.total ?? data.lessons?.length ?? 0,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unable to load course lessons.';
      setLessonsState({ type: 'error', message: msg });
    } finally {
      setIsRetryingLessons(false);
    }
  }, [validCourseId, isRetryingLessons]);


  // Loading skeleton state
  if (viewState.type === 'loading') {
    return (
      <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 py-10 px-4 sm:px-6 lg:px-8">
        <div data-testid="course-detail-loading" className="max-w-4xl mx-auto space-y-6 animate-pulse">
          <div className="h-5 bg-zinc-200 dark:bg-zinc-800 rounded w-32" />
          <div className="h-64 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
          <div className="space-y-3">
            <div className="h-8 bg-zinc-200 dark:bg-zinc-800 rounded w-2/3" />
            <div className="h-4 bg-zinc-200 dark:bg-zinc-800 rounded w-full" />
            <div className="h-4 bg-zinc-200 dark:bg-zinc-800 rounded w-4/5" />
          </div>
        </div>
      </main>
    );
  }

  // Invalid ID or Not Found State
  if (viewState.type === 'invalid_id' || viewState.type === 'not_found') {
    return (
      <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 py-16 px-4 sm:px-6 lg:px-8 flex items-center justify-center">
        <div
          data-testid="course-not-found"
          className="max-w-md w-full text-center space-y-6 p-8 rounded-3xl border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/90 shadow-sm"
        >
          <div className="w-16 h-16 mx-auto rounded-2xl bg-amber-50 dark:bg-amber-950/50 flex items-center justify-center text-3xl select-none">
            📖
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              Course Not Found
            </h1>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
              The course you are looking for does not exist, has an invalid identifier, or may have been removed from the catalog.
            </p>
          </div>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Link
              href="/courses"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 transition-colors shadow-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
            >
              <span>Browse Catalog</span>
            </Link>
            <Link
              href="/"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
            >
              <span>Back Home</span>
            </Link>
          </div>
        </div>
      </main>
    );
  }

  // Error State (Network or Service Unavailable)
  if (viewState.type === 'service_unavailable' || viewState.type === 'network_error') {
    const isServiceDown = viewState.type === 'service_unavailable';
    const message = isServiceDown
      ? 'Database service is temporarily unavailable. Please try again shortly.'
      : viewState.message;

    return (
      <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 py-16 px-4 sm:px-6 lg:px-8 flex items-center justify-center">
        <div
          data-testid="course-error-state"
          className="max-w-md w-full text-center space-y-6 p-8 rounded-3xl border border-red-200 dark:border-red-900/50 bg-red-50/40 dark:bg-red-950/20 shadow-sm"
        >
          <div className="w-16 h-16 mx-auto rounded-2xl bg-red-100 dark:bg-red-900/50 flex items-center justify-center text-red-600 dark:text-red-400">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div className="space-y-2">
            <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              Unable to Load Course
            </h1>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
              {message}
            </p>
          </div>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <button
              type="button"
              onClick={handleRetryCourse}
              disabled={isRetrying}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 transition-colors shadow-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 disabled:opacity-50"
            >
              <span>{isRetrying ? 'Retrying...' : 'Try Again'}</span>
            </button>
            <Link
              href="/courses"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
            >
              <span>Back to Catalog</span>
            </Link>
          </div>
        </div>
      </main>
    );
  }

  // Success State
  const course = viewState.course;
  const levelStyle = getLevelBadgeStyle(course.level);

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 py-10 px-4 sm:px-6 lg:px-8">
      <div data-testid="course-detail-view" className="max-w-4xl mx-auto space-y-8">
        {/* Navigation Breadcrumb */}
        <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
          <Link href="/courses" className="hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            <span>Back to Catalog</span>
          </Link>
          <span>/</span>
          <span className="text-zinc-900 dark:text-zinc-100 font-medium truncate max-w-xs">
            {course.title}
          </span>
        </nav>

        {/* Hero Card (Symmetric & Attractive) */}
        <article className="rounded-3xl border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/90 shadow-xs overflow-hidden">
          {/* Header Banner */}
          <div className="relative w-full py-12 px-6 sm:px-10 bg-gradient-to-br from-indigo-500/10 via-purple-500/10 to-pink-500/10 dark:from-indigo-950/40 dark:via-purple-950/40 dark:to-pink-950/40 border-b border-zinc-100 dark:border-zinc-800/80 flex flex-col items-center text-center space-y-4">
            {/* Thumbnail Emoji */}
            <div className="w-20 h-20 rounded-2xl bg-white/80 dark:bg-zinc-800/80 backdrop-blur-md shadow-sm border border-zinc-200/60 dark:border-zinc-700/60 flex items-center justify-center text-4xl select-none">
              {course.thumbnail || '📚'}
            </div>

            {/* Badges */}
            <div className="flex flex-wrap items-center justify-center gap-2">
              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-white/90 dark:bg-zinc-900/90 text-indigo-700 dark:text-indigo-300 border border-indigo-100 dark:border-indigo-900/50 shadow-xs">
                {course.category}
              </span>
              <span className={`px-3 py-1 rounded-full text-xs font-semibold border shadow-xs ${levelStyle.bg} ${levelStyle.text} ${levelStyle.border}`}>
                {course.level}
              </span>
              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800/60 flex items-center gap-1 shadow-xs">
                <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 20 20" aria-hidden="true">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
                <span>{Number(course.rating).toFixed(1)} Rating</span>
              </span>
            </div>

            {/* Course Title */}
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight text-zinc-900 dark:text-zinc-100 max-w-2xl">
              {course.title}
            </h1>

            {/* Instructor Attribution */}
            <div className="flex items-center gap-2 pt-1">
              <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white text-xs font-bold">
                {course.instructor.charAt(0).toUpperCase()}
              </div>
              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Taught by <span className="font-semibold text-zinc-900 dark:text-zinc-100">{course.instructor}</span>
              </span>
            </div>
          </div>

          {/* Body Section */}
          <div className="p-6 sm:p-10 space-y-8">
            {/* Description */}
            <section className="space-y-3">
              <h2 className="text-base font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                About This Course
              </h2>
              <p className="text-sm sm:text-base text-zinc-600 dark:text-zinc-300 leading-relaxed whitespace-pre-line">
                {course.description}
              </p>
            </section>

            {/* Course Details Grid (Symmetric 4-column spec) */}
            <section aria-label="Course details" className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-6 border-t border-zinc-100 dark:border-zinc-800">
              <div className="p-4 rounded-2xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800 text-center space-y-1">
                <span className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">Duration</span>
                <p className="text-sm font-bold text-zinc-900 dark:text-zinc-100">{course.duration}</p>
              </div>
              <div className="p-4 rounded-2xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800 text-center space-y-1">
                <span className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">Lessons</span>
                <p className="text-sm font-bold text-zinc-900 dark:text-zinc-100">{course.total_lessons} total</p>
              </div>
              <div className="p-4 rounded-2xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800 text-center space-y-1">
                <span className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">Level</span>
                <p className="text-sm font-bold text-zinc-900 dark:text-zinc-100">{course.level}</p>
              </div>
              <div className="p-4 rounded-2xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800 text-center space-y-1">
                <span className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">Price</span>
                <p className="text-sm font-bold text-emerald-600 dark:text-emerald-400">{formatCoursePrice(course.price)}</p>
              </div>
            </section>

            {/* Stage 9: Enrollment Action & Status Card (Symmetric & Attractive) */}
            <section
              data-testid="enrollment-section"
              aria-label="Course enrollment status and action"
              className="p-6 sm:p-7 rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-800/40 shadow-xs space-y-4"
            >
              {enrollmentState.type === 'checking' && (
                <div
                  data-testid="enrollment-checking"
                  className="flex items-center justify-between gap-4 animate-pulse"
                >
                  <div className="space-y-1.5 flex-1">
                    <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-1/3" />
                    <div className="h-3 bg-zinc-200 dark:bg-zinc-700 rounded w-1/2" />
                  </div>
                  <div className="h-10 bg-zinc-200 dark:bg-zinc-700 rounded-xl w-36" />
                </div>
              )}

              {enrollmentState.type === 'not_enrolled' && (
                <div
                  data-testid="enroll-not-enrolled-state"
                  className="flex flex-col sm:flex-row items-center justify-between gap-4"
                >
                  <div className="space-y-1 text-center sm:text-left">
                    <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                      Enrollment Open
                    </h3>
                    <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400">
                      Enroll now to track your learning journey and save your progress.
                    </p>
                  </div>
                  <button
                    type="button"
                    data-testid="enroll-button"
                    onClick={handleEnroll}
                    className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 cursor-pointer"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    <span>Enroll in Course</span>
                  </button>
                </div>
              )}

              {enrollmentState.type === 'enrolling' && (
                <div
                  data-testid="enrollment-in-progress"
                  className="flex flex-col sm:flex-row items-center justify-between gap-4"
                >
                  <div className="space-y-1 text-center sm:text-left">
                    <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                      Processing Enrollment
                    </h3>
                    <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400">
                      Registering your enrollment securely in the database...
                    </p>
                  </div>
                  <button
                    type="button"
                    data-testid="enrolling-button"
                    disabled
                    className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold bg-indigo-600/70 text-white shadow-xs opacity-75 cursor-not-allowed"
                  >
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span>Enrolling...</span>
                  </button>
                </div>
              )}

              {enrollmentState.type === 'enrolled' && (
                <div
                  data-testid="enrolled-badge"
                  className="p-4 sm:p-5 rounded-2xl bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200/80 dark:border-emerald-800/60 flex flex-col sm:flex-row items-center justify-between gap-4"
                >
                  <div className="flex items-center gap-3.5 text-center sm:text-left">
                    <div className="w-10 h-10 rounded-full bg-emerald-100 dark:bg-emerald-900/60 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2 justify-center sm:justify-start">
                        <h3 className="text-sm font-bold text-emerald-800 dark:text-emerald-200">
                          You are enrolled in this course
                        </h3>
                        {enrollmentState.justEnrolled && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-200/80 dark:bg-emerald-900 text-emerald-800 dark:text-emerald-200">
                            New!
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-emerald-700/80 dark:text-emerald-300/80">
                        Progress: {enrollmentState.enrollment?.progress ?? 0}% completed • {enrollmentState.enrollment?.completed_lessons ?? 0} lessons done
                      </p>
                    </div>
                  </div>
                  <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 text-white shadow-xs">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>Active Enrollment</span>
                  </span>
                </div>
              )}

              {enrollmentState.type === 'unauthenticated' && (
                <div
                  data-testid="enroll-unauthenticated"
                  className="flex flex-col sm:flex-row items-center justify-between gap-4"
                >
                  <div className="space-y-1 text-center sm:text-left">
                    <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                      Sign In to Enroll
                    </h3>
                    <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400">
                      Please log in with your learner account to enroll and start learning.
                    </p>
                  </div>
                  <Link
                    href="/login"
                    data-testid="sign-in-to-enroll-link"
                    className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 shadow-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 whitespace-nowrap"
                  >
                    <span>Sign In to Enroll</span>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                    </svg>
                  </Link>
                </div>
              )}

              {enrollmentState.type === 'error' && (
                <div
                  data-testid="enroll-error"
                  className="p-4 rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50/50 dark:bg-red-950/20 flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left"
                >
                  <div className="space-y-0.5">
                    <p className="text-xs sm:text-sm font-semibold text-red-700 dark:text-red-300">
                      Enrollment Notice
                    </p>
                    <p className="text-xs text-red-600/90 dark:text-red-400/90">
                      {enrollmentState.message}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleEnroll}
                    className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-red-600 hover:bg-red-500 text-white shadow-xs transition-colors shrink-0"
                  >
                    Try Again
                  </button>
                </div>
              )}
            </section>

            {/* Stage 10: Course Curriculum / Lessons Section (Symmetric & Attractive) */}
            <section
              data-testid="lessons-section"
              aria-label="Course Curriculum and Lessons"
              className="p-6 sm:p-8 rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 shadow-xs space-y-6"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-100 dark:border-zinc-800/80 pb-4">
                <div className="space-y-0.5">
                  <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                    Course Curriculum
                  </h2>
                  <p className="text-xs sm:text-sm text-zinc-500 dark:text-zinc-400">
                    Structured lessons and learning modules for this course.
                  </p>
                </div>
                {lessonsState.type === 'loaded' && (
                  <span className="text-xs font-semibold px-3 py-1 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 self-start sm:self-auto">
                    {lessonsState.total} {lessonsState.total === 1 ? 'lesson' : 'lessons'} published
                  </span>
                )}
              </div>

              {/* Loading State */}
              {lessonsState.type === 'loading' && (
                <div data-testid="lessons-loading" className="space-y-3 animate-pulse">
                  <div className="h-16 bg-zinc-100 dark:bg-zinc-800/60 rounded-xl" />
                  <div className="h-16 bg-zinc-100 dark:bg-zinc-800/60 rounded-xl" />
                  <div className="h-16 bg-zinc-100 dark:bg-zinc-800/60 rounded-xl" />
                </div>
              )}

              {/* Error State */}
              {lessonsState.type === 'error' && (
                <div
                  data-testid="lessons-error"
                  className="p-5 rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50/50 dark:bg-red-950/20 flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left"
                >
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-red-700 dark:text-red-300">
                      Unable to Load Lessons
                    </p>
                    <p className="text-xs text-red-600/90 dark:text-red-400/90">
                      {lessonsState.message}
                    </p>
                  </div>
                  <button
                    type="button"
                    data-testid="lessons-retry-button"
                    onClick={handleRetryLessons}
                    disabled={isRetryingLessons}
                    className="px-4 py-2 rounded-xl text-xs font-semibold bg-red-600 hover:bg-red-500 text-white shadow-xs transition-colors shrink-0 disabled:opacity-50 cursor-pointer"
                  >
                    {isRetryingLessons ? 'Retrying...' : 'Retry Lessons'}
                  </button>
                </div>
              )}

              {/* Empty State */}
              {lessonsState.type === 'loaded' && lessonsState.lessons.length === 0 && (
                <div
                  data-testid="lessons-empty"
                  className="py-10 px-6 rounded-2xl border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-950/40 text-center space-y-3"
                >
                  <div className="w-12 h-12 mx-auto rounded-xl bg-zinc-100 dark:bg-zinc-800/80 flex items-center justify-center text-2xl select-none">
                    📚
                  </div>
                  <div className="max-w-md mx-auto space-y-1">
                    <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                      No Lessons Available Yet
                    </h3>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
                      The instructor has not published lesson modules for this course yet. Check back soon for the full syllabus.
                    </p>
                  </div>
                </div>
              )}

              {/* Lessons List State */}
              {lessonsState.type === 'loaded' && lessonsState.lessons.length > 0 && (
                <div data-testid="lessons-list" className="space-y-3">
                  {lessonsState.lessons.map((lesson, idx) => (
                    <div
                      key={lesson.id}
                      data-testid={`lesson-item-${lesson.id}`}
                      className="p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800 hover:border-indigo-300 dark:hover:border-indigo-700/60 bg-zinc-50/50 dark:bg-zinc-800/30 hover:bg-zinc-50 dark:hover:bg-zinc-800/60 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                    >
                      <div className="flex items-start sm:items-center gap-3.5">
                        <span className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 text-xs font-bold flex items-center justify-center shrink-0">
                          {idx + 1}
                        </span>
                        <div className="space-y-0.5">
                          <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                            {lesson.title}
                          </h4>
                          {lesson.description && (
                            <p className="text-xs text-zinc-500 dark:text-zinc-400 line-clamp-1">
                              {lesson.description}
                            </p>
                          )}
                        </div>
                      </div>
                      <Link
                        href={`/courses/${course.id}/lessons/${lesson.id}`}
                        data-testid={`lesson-link-${lesson.id}`}
                        className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 transition-colors shadow-xs shrink-0 self-end sm:self-auto"
                      >
                        <span>View Lesson</span>
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </section>


            {/* Course Value & Catalog Back Navigation */}
            <div className="p-5 rounded-2xl bg-gradient-to-r from-indigo-50/50 via-purple-50/50 to-pink-50/50 dark:from-indigo-950/20 dark:via-purple-950/20 dark:to-pink-950/20 border border-indigo-100 dark:border-indigo-900/40 flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="space-y-0.5 text-center sm:text-left">
                <span className="text-xs font-semibold text-indigo-700 dark:text-indigo-300">
                  Course Value &amp; Points
                </span>
                <p className="text-sm text-zinc-700 dark:text-zinc-300">
                  Standard tuition: <span className="font-bold">{formatCoursePrice(course.price)}</span>
                  {course.points_price > 0 && (
                    <span> • Redeemable for <span className="font-bold text-indigo-600 dark:text-indigo-400">{formatPointsPrice(course.points_price)}</span></span>
                  )}
                </p>
              </div>
              <Link
                href="/courses"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 transition-colors shadow-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 whitespace-nowrap"
              >
                <span>Back to All Courses</span>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </Link>
            </div>
          </div>
        </article>
      </div>
    </main>
  );
}

export default function CourseDetailPage({ params }: PageProps) {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 py-10 px-4 sm:px-6 lg:px-8">
          <div className="max-w-4xl mx-auto space-y-6 animate-pulse">
            <div className="h-5 bg-zinc-200 dark:bg-zinc-800 rounded w-32" />
            <div className="h-64 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
          </div>
        </main>
      }
    >
      <CourseDetailContent params={params} />
    </Suspense>
  );
}
