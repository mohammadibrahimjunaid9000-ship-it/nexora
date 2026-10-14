'use client';

import React, { use, useEffect, useState, useCallback, Suspense } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { PublicUserProfile } from '@/lib/types';
import { ApiError, getPublicUserProfile } from '@/lib/api';
import { parseUserId } from '@/lib/profile-utils';
import { PublicProfileCard } from '@/components/profile/PublicProfileCard';

interface PageProps {
  params: Promise<{ userId: string }>;
}

type ViewState =
  | { type: 'loading' }
  | { type: 'invalid_id' }
  | { type: 'not_found' }
  | { type: 'service_unavailable' }
  | { type: 'network_error'; message: string }
  | { type: 'success'; profile: PublicUserProfile };

function PublicProfileContent({ params }: PageProps) {
  const resolvedParams = use(params);
  const rawUserId = resolvedParams?.userId;
  const router = useRouter();

  const validUserId = parseUserId(rawUserId);

  const [viewState, setViewState] = useState<ViewState>(() =>
    validUserId === null ? { type: 'invalid_id' } : { type: 'loading' }
  );
  const [isRetrying, setIsRetrying] = useState<boolean>(false);

  useEffect(() => {
    if (validUserId === null) return;

    let isMounted = true;

    getPublicUserProfile(validUserId)
      .then((data) => {
        if (isMounted) {
          setViewState({ type: 'success', profile: data });
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
                message: err.message || 'Unable to load profile.',
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
  }, [validUserId]);

  const handleRetry = useCallback(async () => {
    if (validUserId === null || isRetrying) return;
    setIsRetrying(true);

    try {
      const data = await getPublicUserProfile(validUserId);
      setViewState({ type: 'success', profile: data });
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setViewState({ type: 'not_found' });
        } else if (err.status === 503) {
          setViewState({ type: 'service_unavailable' });
        } else {
          setViewState({
            type: 'network_error',
            message: err.message || 'Unable to load profile.',
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
  }, [validUserId, isRetrying]);

  const handleGoBack = () => {
    if (window.history.length > 1) {
      router.back();
    } else {
      router.push('/');
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex flex-col bg-zinc-50 dark:bg-black font-sans text-zinc-900 dark:text-zinc-100 antialiased">
      {/* Sub-navigation */}
      <div className="w-full max-w-5xl mx-auto px-4 sm:px-6 pt-6 flex items-center justify-between text-sm">
        <nav aria-label="Breadcrumb navigation" className="flex items-center gap-2 text-zinc-500 dark:text-zinc-400">
          <Link href="/" className="hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors">
            Home
          </Link>
          <span className="text-zinc-300 dark:text-zinc-700">/</span>
          <span className="text-zinc-500 dark:text-zinc-400">Users</span>
          <span className="text-zinc-300 dark:text-zinc-700">/</span>
          <span className="font-medium text-zinc-900 dark:text-zinc-100">
            {validUserId !== null ? `#${validUserId}` : 'Profile'}
          </span>
        </nav>
        <button
          type="button"
          onClick={handleGoBack}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded"
          aria-label="Go back to previous screen"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Go Back
        </button>
      </div>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col items-center justify-center py-8 sm:py-12 px-4">
        {/* Loading State */}
        {viewState.type === 'loading' && (
          <div className="w-full max-w-xl mx-auto px-4 py-8 animate-pulse" data-testid="public-profile-loading">
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-8 shadow-sm text-center">
              <div className="mx-auto w-24 h-24 rounded-full bg-zinc-200 dark:bg-zinc-800 ring-4 ring-zinc-100 dark:ring-zinc-800/50" />
              <div className="h-6 w-40 bg-zinc-200 dark:bg-zinc-800 rounded-lg mx-auto mt-5" />
              <div className="h-5 w-20 bg-zinc-200 dark:bg-zinc-800 rounded-full mx-auto mt-3" />
              <div className="h-14 bg-zinc-100 dark:bg-zinc-800/50 rounded-2xl mt-8" />
            </div>
          </div>
        )}

        {/* Invalid ID State */}
        {viewState.type === 'invalid_id' && (
          <div className="w-full max-w-md mx-auto px-4 py-12 text-center" data-testid="public-profile-invalid">
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-8 shadow-sm">
              <div className="mx-auto w-16 h-16 rounded-2xl flex items-center justify-center bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 border border-amber-200/60 dark:border-amber-900/40 mb-5">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
              </div>
              <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                Invalid User ID
              </h1>
              <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400 max-w-sm mx-auto leading-relaxed">
                The requested user ID is not valid. User identifiers must be positive whole numbers.
              </p>
              <div className="mt-8 flex justify-center">
                <button
                  type="button"
                  onClick={handleGoBack}
                  className="px-6 py-2.5 rounded-xl text-sm font-medium bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2"
                >
                  Go Back
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 404 User Not Found State */}
        {viewState.type === 'not_found' && (
          <div className="w-full max-w-md mx-auto px-4 py-12 text-center" data-testid="public-profile-not-found">
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-8 shadow-sm">
              <div className="mx-auto w-16 h-16 rounded-2xl flex items-center justify-center bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 border border-zinc-200/60 dark:border-zinc-700/60 mb-5">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                  />
                </svg>
              </div>
              <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                User not found
              </h1>
              <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400 max-w-sm mx-auto leading-relaxed">
                This profile doesn&apos;t exist or is no longer available.
              </p>
              <div className="mt-8 flex justify-center gap-3">
                <button
                  type="button"
                  onClick={handleGoBack}
                  className="px-6 py-2.5 rounded-xl text-sm font-medium bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2"
                >
                  Go Back
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 503 Service Unavailable State */}
        {viewState.type === 'service_unavailable' && (
          <div className="w-full max-w-md mx-auto px-4 py-12 text-center" data-testid="public-profile-503">
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-8 shadow-sm">
              <div className="mx-auto w-16 h-16 rounded-2xl flex items-center justify-center bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 border border-amber-200/60 dark:border-amber-900/40 mb-5">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
              <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                Profile temporarily unavailable
              </h1>
              <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400 max-w-sm mx-auto leading-relaxed">
                We&apos;re having trouble loading this profile right now. Please try again.
              </p>
              <div className="mt-8 flex items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={handleRetry}
                  disabled={isRetrying}
                  className="px-5 py-2.5 rounded-xl text-sm font-medium bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2"
                >
                  {isRetrying ? 'Retrying...' : 'Retry'}
                </button>
                <button
                  type="button"
                  onClick={handleGoBack}
                  className="px-5 py-2.5 rounded-xl text-sm font-medium border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 bg-transparent hover:bg-zinc-50 dark:hover:bg-zinc-800/60 transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-400"
                >
                  Go Back
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Network / Connection Error State */}
        {viewState.type === 'network_error' && (
          <div className="w-full max-w-md mx-auto px-4 py-12 text-center" data-testid="public-profile-error">
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-8 shadow-sm">
              <div className="mx-auto w-16 h-16 rounded-2xl flex items-center justify-center bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 border border-red-200/60 dark:border-red-900/40 mb-5">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
              <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                Connection error
              </h1>
              <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400 max-w-sm mx-auto leading-relaxed">
                {viewState.message || 'Unable to connect to the server. Please try again.'}
              </p>
              <div className="mt-8 flex items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={handleRetry}
                  disabled={isRetrying}
                  className="px-5 py-2.5 rounded-xl text-sm font-medium bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2"
                >
                  {isRetrying ? 'Retrying...' : 'Retry'}
                </button>
                <button
                  type="button"
                  onClick={handleGoBack}
                  className="px-5 py-2.5 rounded-xl text-sm font-medium border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 bg-transparent hover:bg-zinc-50 dark:hover:bg-zinc-800/60 transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-400"
                >
                  Go Back
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Success State */}
        {viewState.type === 'success' && (
          <div className="w-full flex flex-col items-center">
            <PublicProfileCard profile={viewState.profile} />
            <div className="mt-4">
              <button
                type="button"
                onClick={handleGoBack}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 bg-white dark:bg-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-zinc-400"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                Go Back
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Symmetric Footer */}
      <footer className="w-full border-t border-zinc-200/80 dark:border-zinc-800/80 bg-white/40 dark:bg-zinc-950/40 py-6">
        <div className="max-w-5xl mx-auto px-4 text-center text-xs text-zinc-500 dark:text-zinc-500">
          Nexora Platform &bull; Community Member Profile
        </div>
      </footer>
    </div>
  );
}

function PublicProfileLoadingShell() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-8 sm:py-12 px-4">
      <div className="w-full max-w-xl mx-auto px-4 py-8 animate-pulse">
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-8 shadow-sm text-center">
          <div className="mx-auto w-24 h-24 rounded-full bg-zinc-200 dark:bg-zinc-800 ring-4 ring-zinc-100 dark:ring-zinc-800/50" />
          <div className="h-6 w-40 bg-zinc-200 dark:bg-zinc-800 rounded-lg mx-auto mt-5" />
          <div className="h-5 w-20 bg-zinc-200 dark:bg-zinc-800 rounded-full mx-auto mt-3" />
          <div className="h-14 bg-zinc-100 dark:bg-zinc-800/50 rounded-2xl mt-8" />
        </div>
      </div>
    </div>
  );
}

export default function PublicUserProfilePage({ params }: PageProps) {
  return (
    <Suspense fallback={<PublicProfileLoadingShell />}>
      <PublicProfileContent params={params} />
    </Suspense>
  );
}
