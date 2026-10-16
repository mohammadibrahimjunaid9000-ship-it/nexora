'use client';

import React, { use, useEffect, useState, useCallback, Suspense } from 'react';
import Link from 'next/link';
import type { LessonDetail } from '@/lib/types';
import { ApiError, getLessonById } from '@/lib/api';
import { parseCourseId } from '@/lib/course-utils';

interface PageProps {
  params: Promise<{ courseId: string; lessonId: string }>;
}

type LessonViewState =
  | { type: 'loading' }
  | { type: 'invalid_id' }
  | { type: 'not_found' }
  | { type: 'service_unavailable' }
  | { type: 'network_error'; message: string }
  | { type: 'success'; lesson: LessonDetail };

function LessonDetailContent({ params }: PageProps) {
  const resolvedParams = use(params);
  const rawCourseId = resolvedParams?.courseId;
  const rawLessonId = resolvedParams?.lessonId;

  const validCourseId = parseCourseId(rawCourseId);
  const validLessonId = parseCourseId(rawLessonId);

  const isInvalid = validCourseId === null || validLessonId === null;

  const [viewState, setViewState] = useState<LessonViewState>(() =>
    isInvalid ? { type: 'invalid_id' } : { type: 'loading' }
  );
  const [isRetrying, setIsRetrying] = useState<boolean>(false);

  useEffect(() => {
    if (validCourseId === null || validLessonId === null) {
      return;
    }

    let isMounted = true;


    getLessonById(validCourseId, validLessonId)
      .then((data) => {
        if (isMounted) {
          setViewState({ type: 'success', lesson: data });
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
                message: err.message || 'Unable to load lesson details.',
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

    return () => {
      isMounted = false;
    };
  }, [validCourseId, validLessonId]);

  const handleRetry = useCallback(async () => {
    if (validCourseId === null || validLessonId === null || isRetrying) return;
    setIsRetrying(true);
    setViewState({ type: 'loading' });

    try {
      const data = await getLessonById(validCourseId, validLessonId);
      setViewState({ type: 'success', lesson: data });

    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setViewState({ type: 'not_found' });
        } else if (err.status === 503) {
          setViewState({ type: 'service_unavailable' });
        } else {
          setViewState({
            type: 'network_error',
            message: err.message || 'Unable to load lesson details.',
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
  }, [validCourseId, validLessonId, isRetrying]);

  const backCourseHref = validCourseId ? `/courses/${validCourseId}` : '/courses';

  // Loading skeleton state
  if (viewState.type === 'loading') {
    return (
      <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 py-10 px-4 sm:px-6 lg:px-8">
        <div data-testid="lesson-loading" className="max-w-4xl mx-auto space-y-6 animate-pulse">
          <div className="h-5 bg-zinc-200 dark:bg-zinc-800 rounded w-40" />
          <div className="h-48 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
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
          data-testid="lesson-not-found"
          className="max-w-md w-full text-center space-y-6 p-8 rounded-3xl border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/90 shadow-sm"
        >
          <div className="w-16 h-16 mx-auto rounded-2xl bg-amber-50 dark:bg-amber-950/50 flex items-center justify-center text-3xl select-none">
            🔍
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              Lesson Not Found
            </h1>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
              The requested lesson does not exist in this course, has an invalid identifier, or has not been published yet.
            </p>
          </div>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Link
              href={backCourseHref}
              data-testid="back-to-course-link"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 transition-colors shadow-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
            >
              <span>Back to Course</span>
            </Link>
            <Link
              href="/courses"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
            >
              <span>All Courses</span>
            </Link>
          </div>
        </div>
      </main>
    );
  }

  // Error State
  if (viewState.type === 'service_unavailable' || viewState.type === 'network_error') {
    const isServiceDown = viewState.type === 'service_unavailable';
    const message = isServiceDown
      ? 'Database service is temporarily unavailable. Please try again shortly.'
      : viewState.message;

    return (
      <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 py-16 px-4 sm:px-6 lg:px-8 flex items-center justify-center">
        <div
          data-testid="lesson-error-state"
          className="max-w-md w-full text-center space-y-6 p-8 rounded-3xl border border-red-200 dark:border-red-900/50 bg-red-50/40 dark:bg-red-950/20 shadow-sm"
        >
          <div className="w-16 h-16 mx-auto rounded-2xl bg-red-100 dark:bg-red-900/50 flex items-center justify-center text-red-600 dark:text-red-400">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div className="space-y-2">
            <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              Unable to Load Lesson
            </h1>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
              {message}
            </p>
          </div>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <button
              type="button"
              data-testid="lesson-retry-button"
              onClick={handleRetry}
              disabled={isRetrying}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 transition-colors shadow-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 disabled:opacity-50 cursor-pointer"
            >
              <span>{isRetrying ? 'Retrying...' : 'Try Again'}</span>
            </button>
            <Link
              href={backCourseHref}
              data-testid="back-to-course-link"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
            >
              <span>Back to Course</span>
            </Link>
          </div>
        </div>
      </main>
    );
  }

  // Success State
  const lesson = viewState.lesson;

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 py-10 px-4 sm:px-6 lg:px-8">
      <div data-testid="lesson-detail-view" className="max-w-4xl mx-auto space-y-8">
        {/* Navigation Breadcrumb */}
        <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs sm:text-sm text-zinc-500 dark:text-zinc-400">
          <Link
            href="/courses"
            className="hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
          >
            Courses
          </Link>
          <span>/</span>
          <Link
            href={backCourseHref}
            data-testid="back-to-course-link"
            className="hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
          >
            Course #{validCourseId}
          </Link>
          <span>/</span>
          <span className="text-zinc-900 dark:text-zinc-100 font-medium truncate max-w-xs">
            Lesson #{lesson.id}
          </span>
        </nav>

        {/* Lesson Container Card (Symmetric & Attractive) */}
        <article className="rounded-3xl border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm overflow-hidden">
          {/* Header Banner */}
          <div className="p-6 sm:p-10 border-b border-zinc-100 dark:border-zinc-800 bg-gradient-to-br from-indigo-500/10 via-purple-500/5 to-transparent">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/70 text-indigo-700 dark:text-indigo-300 border border-indigo-200/60 dark:border-indigo-800/60">
                <span>Lesson #{lesson.id}</span>
              </span>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                Course ID: {lesson.course_id}
              </span>
            </div>

            <h1
              data-testid="lesson-title"
              className="text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-900 dark:text-zinc-100"
            >
              {lesson.title}
            </h1>
          </div>

          {/* Lesson Body */}
          <div className="p-6 sm:p-10 space-y-8">
            <section className="space-y-3">
              <h2 className="text-base font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
                Lesson Overview
              </h2>
              <div
                data-testid="lesson-description"
                className="text-sm sm:text-base text-zinc-600 dark:text-zinc-300 leading-relaxed whitespace-pre-line"
              >
                {lesson.description || 'No additional lesson notes provided for this module.'}
              </div>
            </section>

            {/* Back to Course Action Card */}
            <div className="pt-6 border-t border-zinc-100 dark:border-zinc-800 flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="space-y-0.5 text-center sm:text-left">
                <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">
                  Course Navigation
                </span>
                <p className="text-sm text-zinc-700 dark:text-zinc-300">
                  Return to the course curriculum to view other lessons and enrollment details.
                </p>
              </div>
              <Link
                href={backCourseHref}
                data-testid="back-to-course-button"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 transition-colors shadow-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 whitespace-nowrap"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                <span>Back to Course</span>
              </Link>
            </div>
          </div>
        </article>
      </div>
    </main>
  );
}

export default function LessonDetailPage({ params }: PageProps) {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 py-10 px-4 sm:px-6 lg:px-8">
          <div className="max-w-4xl mx-auto space-y-6 animate-pulse">
            <div className="h-5 bg-zinc-200 dark:bg-zinc-800 rounded w-40" />
            <div className="h-48 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
          </div>
        </main>
      }
    >
      <LessonDetailContent params={params} />
    </Suspense>
  );
}
