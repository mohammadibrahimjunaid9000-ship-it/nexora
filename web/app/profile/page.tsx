'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import type { UserProfileResponse } from '@/lib/types';
import {
  ApiError,
  getAuthenticatedProfile,
  updateAuthenticatedProfileName,
} from '@/lib/api';
import { ProfileCard } from '@/components/profile/ProfileCard';
import { ProfileLoading } from '@/components/profile/ProfileLoading';
import { ProfileError } from '@/components/profile/ProfileError';

interface ErrorState {
  status?: number;
  message: string;
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<UserProfileResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<ErrorState | null>(null);

  useEffect(() => {
    let isMounted = true;

    getAuthenticatedProfile()
      .then((data) => {
        if (isMounted) {
          setProfile(data);
          setError(null);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          if (err instanceof ApiError) {
            setError({
              status: err.status,
              message: err.message,
            });
          } else if (err instanceof Error) {
            setError({
              message: err.message,
            });
          } else {
            setError({
              message: 'An unexpected error occurred while loading your profile.',
            });
          }
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleRetry = useCallback(async () => {
    setIsRetrying(true);
    setError(null);

    try {
      const data = await getAuthenticatedProfile();
      setProfile(data);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError({
          status: err.status,
          message: err.message,
        });
      } else if (err instanceof Error) {
        setError({
          message: err.message,
        });
      } else {
        setError({
          message: 'An unexpected error occurred while loading your profile.',
        });
      }
    } finally {
      setIsRetrying(false);
    }
  }, []);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      const updated = await getAuthenticatedProfile();
      setProfile(updated);
    } catch (err: unknown) {
      // If refresh fails due to session expiry (401), update error state
      if (err instanceof ApiError && err.status === 401) {
        setProfile(null);
        setError({
          status: 401,
          message: err.message,
        });
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleUpdateName = async (newName: string): Promise<boolean> => {
    try {
      const updated = await updateAuthenticatedProfileName({ name: newName });
      setProfile(updated);
      return true;
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        throw new Error(err.message);
      }
      if (err instanceof Error) {
        throw err;
      }
      throw new Error('Failed to update name.');
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-zinc-50 dark:bg-black font-sans text-zinc-900 dark:text-zinc-100 antialiased">
      {/* Symmetric Header / Minimal Navigation */}
      <header className="w-full border-b border-zinc-200/80 dark:border-zinc-800/80 bg-white/80 dark:bg-zinc-950/80 backdrop-blur-md sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 group transition-opacity hover:opacity-90"
            aria-label="Nexora Home"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center text-white font-bold text-base shadow-sm">
              N
            </div>
            <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-zinc-900 to-zinc-700 dark:from-white dark:to-zinc-300 bg-clip-text text-transparent">
              NEXORA
            </span>
          </Link>

          <nav aria-label="Breadcrumb navigation" className="flex items-center gap-3 text-sm">
            <Link
              href="/"
              className="text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 transition-colors"
            >
              Home
            </Link>
            <span className="text-zinc-300 dark:text-zinc-700">/</span>
            <span className="font-medium text-zinc-900 dark:text-zinc-100">Profile</span>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col items-center justify-center py-8 sm:py-12 px-4">
        <div className="w-full max-w-2xl text-center mb-4">
          <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-4xl">
            User Profile
          </h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            Manage your personal Nexora account details and view your platform achievements.
          </p>
        </div>

        {isLoading ? (
          <ProfileLoading />
        ) : error ? (
          <ProfileError
            status={error.status}
            message={error.message}
            onRetry={handleRetry}
            isRetrying={isRetrying}
          />
        ) : profile ? (
          <ProfileCard
            profile={profile}
            onUpdateName={handleUpdateName}
            onRefresh={handleRefresh}
            isRefreshing={isRefreshing}
          />
        ) : null}
      </main>

      {/* Symmetric Footer */}
      <footer className="w-full border-t border-zinc-200/80 dark:border-zinc-800/80 bg-white/40 dark:bg-zinc-950/40 py-6">
        <div className="max-w-5xl mx-auto px-4 text-center text-xs text-zinc-500 dark:text-zinc-500">
          Nexora Platform &bull; Authenticated Profile
        </div>
      </footer>
    </div>
  );
}
