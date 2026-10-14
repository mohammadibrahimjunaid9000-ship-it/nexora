'use client';

import React from 'react';

export function ProfileLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="w-full max-w-2xl mx-auto px-4 py-8 animate-pulse"
      data-testid="profile-loading"
    >
      <span className="sr-only">Loading your profile details...</span>
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-8 shadow-sm">
        {/* Top Avatar Skeleton */}
        <div className="flex flex-col items-center">
          <div className="w-24 h-24 rounded-full bg-zinc-200 dark:bg-zinc-800 ring-4 ring-zinc-100 dark:ring-zinc-800/50" />
          <div className="h-6 w-44 bg-zinc-200 dark:bg-zinc-800 rounded-lg mt-5" />
          <div className="h-5 w-24 bg-zinc-200 dark:bg-zinc-800 rounded-full mt-3" />
        </div>

        {/* Symmetric 2x2 Grid Skeleton */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-8">
          <div className="h-24 bg-zinc-100 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800 rounded-2xl p-4" />
          <div className="h-24 bg-zinc-100 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800 rounded-2xl p-4" />
          <div className="h-24 bg-zinc-100 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800 rounded-2xl p-4" />
          <div className="h-24 bg-zinc-100 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800 rounded-2xl p-4" />
        </div>

        {/* Action Button Skeleton */}
        <div className="flex justify-center gap-4 mt-8 pt-6 border-t border-zinc-100 dark:border-zinc-800">
          <div className="h-10 w-32 bg-zinc-200 dark:bg-zinc-800 rounded-xl" />
          <div className="h-10 w-28 bg-zinc-200 dark:bg-zinc-800 rounded-xl" />
        </div>
      </div>
    </div>
  );
}
