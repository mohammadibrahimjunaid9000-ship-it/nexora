'use client';

import React from 'react';

interface ProfileErrorProps {
  status?: number;
  message?: string;
  onRetry: () => void;
  isRetrying?: boolean;
}

export function ProfileError({ status, message, onRetry, isRetrying = false }: ProfileErrorProps) {
  const isAuthError = status === 401;
  const isServiceUnavailable = status === 503;

  let title = 'Error Loading Profile';
  let description =
    message || 'An unexpected error occurred while loading your profile. Please try again.';

  if (isAuthError) {
    title = 'Authentication Required';
    description =
      'You are not currently signed in or your session has expired. Please sign in to view your Nexora profile.';
  } else if (isServiceUnavailable) {
    title = 'Service Temporarily Unavailable';
    description =
      'The database service is currently unavailable. Your data is safe; please try again in a moment.';
  } else if (
    message?.toLowerCase().includes('failed to fetch') ||
    message?.toLowerCase().includes('network') ||
    message?.toLowerCase().includes('connection')
  ) {
    title = 'Connection Error';
    description =
      'Unable to connect to the Nexora API. Please check your internet connection or server status.';
  }

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="w-full max-w-xl mx-auto px-4 py-12"
      data-testid="profile-error"
    >
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-8 shadow-sm text-center">
        {/* Symmetric Centered Icon */}
        <div className="mx-auto w-16 h-16 rounded-2xl flex items-center justify-center bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 border border-red-200/60 dark:border-red-900/40 mb-5">
          {isAuthError ? (
            <svg
              className="w-8 h-8"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
              />
            </svg>
          ) : (
            <svg
              className="w-8 h-8"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          )}
        </div>

        <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">{title}</h2>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400 max-w-md mx-auto leading-relaxed">
          {description}
        </p>

        {/* Action Buttons */}
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
          {isAuthError ? (
            <a
              href="/login"
              className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-2.5 rounded-xl text-sm font-medium bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 transition-colors shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-zinc-900 dark:focus-visible:ring-zinc-100"
            >
              Sign In
            </a>
          ) : null}

          <button
            type="button"
            onClick={onRetry}
            disabled={isRetrying}
            aria-busy={isRetrying}
            className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-2.5 rounded-xl text-sm font-medium border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-200 bg-transparent hover:bg-zinc-50 dark:hover:bg-zinc-800/60 transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-zinc-500"
          >
            {isRetrying ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-current"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v8H4z"
                  />
                </svg>
                Retrying...
              </>
            ) : (
              'Retry'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
