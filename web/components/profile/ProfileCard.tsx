'use client';

import React, { useState } from 'react';
import type { UserProfileResponse } from '@/lib/types';
import { formatRoleName, formatJoinedDate } from '@/lib/profile-utils';
import { ProfileEditForm } from './ProfileEditForm';

export { formatRoleName, formatJoinedDate };

interface ProfileCardProps {
  profile: UserProfileResponse;
  onUpdateName: (newName: string) => Promise<boolean>;
  onRefresh: () => Promise<void>;
  isRefreshing: boolean;
}

export function ProfileCard({
  profile,
  onUpdateName,
  onRefresh,
  isRefreshing,
}: ProfileCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const initial = (profile.name?.trim()?.charAt(0) || 'U').toUpperCase();
  const roleDisplay = formatRoleName(profile.role);
  const joinedDateDisplay = formatJoinedDate(profile.joined_at);

  const handleSave = async (newName: string) => {
    setIsSaving(true);
    setSaveError(null);
    try {
      const ok = await onUpdateName(newName);
      if (ok) {
        setIsEditing(false);
        setSuccessMessage('Profile name updated successfully.');
        setTimeout(() => setSuccessMessage(null), 4000);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update name.';
      setSaveError(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setSaveError(null);
  };

  return (
    <div className="w-full max-w-2xl mx-auto px-4 py-8" data-testid="profile-card">
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-6 sm:p-8 shadow-sm">
        {/* Success Alert Banner */}
        {successMessage && (
          <div
            role="status"
            className="mb-6 flex items-center justify-between p-3.5 rounded-2xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300 text-sm font-medium transition-all"
          >
            <div className="flex items-center gap-2.5">
              <svg
                className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
              <span>{successMessage}</span>
            </div>
            <button
              type="button"
              onClick={() => setSuccessMessage(null)}
              className="text-emerald-600 hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-200 text-xs font-semibold px-2 py-1 rounded"
              aria-label="Dismiss alert"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Symmetric Hero / Identity Section */}
        <div className="flex flex-col items-center text-center">
          <div
            className="w-24 h-24 rounded-full bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-600 text-white font-bold text-3xl shadow-md ring-4 ring-indigo-500/10 dark:ring-indigo-400/20 flex items-center justify-center select-none"
            aria-hidden="true"
          >
            {initial}
          </div>

          <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mt-4 tracking-tight">
            {profile.name}
          </h2>

          <div className="mt-2.5 inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200/60 dark:border-indigo-800/60">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-600 dark:bg-indigo-400" />
            {roleDisplay}
          </div>
        </div>

        {/* Conditional Edit Form or Symmetric Info Grid */}
        {isEditing ? (
          <ProfileEditForm
            currentName={profile.name}
            onSave={handleSave}
            onCancel={handleCancel}
            isSaving={isSaving}
            serverError={saveError}
          />
        ) : (
          <>
            {/* Symmetric 2x2 Information Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-8">
              {/* Email Card */}
              <div className="flex items-center gap-3.5 p-4 rounded-2xl bg-zinc-50/70 dark:bg-zinc-800/40 border border-zinc-200/80 dark:border-zinc-800">
                <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0 border border-blue-200/40 dark:border-blue-900/40">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                    />
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <span className="block text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Email Address
                  </span>
                  <span className="block text-sm font-semibold text-zinc-900 dark:text-zinc-100 truncate mt-0.5">
                    {profile.email}
                  </span>
                </div>
              </div>

              {/* Role Card */}
              <div className="flex items-center gap-3.5 p-4 rounded-2xl bg-zinc-50/70 dark:bg-zinc-800/40 border border-zinc-200/80 dark:border-zinc-800">
                <div className="w-10 h-10 rounded-xl bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400 flex items-center justify-center shrink-0 border border-purple-200/40 dark:border-purple-900/40">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                    />
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <span className="block text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Account Role
                  </span>
                  <span className="block text-sm font-semibold text-zinc-900 dark:text-zinc-100 truncate mt-0.5">
                    {roleDisplay}
                  </span>
                </div>
              </div>

              {/* Points Card */}
              <div className="flex items-center gap-3.5 p-4 rounded-2xl bg-zinc-50/70 dark:bg-zinc-800/40 border border-zinc-200/80 dark:border-zinc-800">
                <div className="w-10 h-10 rounded-xl bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0 border border-amber-200/40 dark:border-amber-900/40">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <span className="block text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Points Earned
                  </span>
                  <span className="block text-sm font-semibold text-zinc-900 dark:text-zinc-100 truncate mt-0.5">
                    {profile.points.toLocaleString()} pts
                  </span>
                </div>
              </div>

              {/* Member Since Card */}
              <div className="flex items-center gap-3.5 p-4 rounded-2xl bg-zinc-50/70 dark:bg-zinc-800/40 border border-zinc-200/80 dark:border-zinc-800">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0 border border-emerald-200/40 dark:border-emerald-900/40">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                    />
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <span className="block text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Member Since
                  </span>
                  <span className="block text-sm font-semibold text-zinc-900 dark:text-zinc-100 truncate mt-0.5">
                    {joinedDateDisplay}
                  </span>
                </div>
              </div>
            </div>

            {/* Symmetrical Action Buttons */}
            <div className="flex items-center justify-center gap-3.5 mt-8 pt-6 border-t border-zinc-100 dark:border-zinc-800">
              <button
                type="button"
                onClick={() => setIsEditing(true)}
                className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 text-white transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                  />
                </svg>
                Edit Name
              </button>

              <button
                type="button"
                onClick={onRefresh}
                disabled={isRefreshing}
                className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 bg-transparent hover:bg-zinc-50 dark:hover:bg-zinc-800/60 transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-zinc-400"
                aria-label="Refresh profile"
              >
                <svg
                  className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
                {isRefreshing ? 'Refreshing...' : 'Refresh'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
