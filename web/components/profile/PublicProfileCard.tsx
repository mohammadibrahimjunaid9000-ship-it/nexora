'use client';

import React from 'react';
import type { PublicUserProfile } from '@/lib/types';
import { formatRoleName, getInitials } from '@/lib/profile-utils';

interface PublicProfileCardProps {
  profile: PublicUserProfile;
}

export function PublicProfileCard({ profile }: PublicProfileCardProps) {
  const initials = getInitials(profile.name);
  const roleDisplay = formatRoleName(profile.role);

  return (
    <div className="w-full max-w-xl mx-auto px-4 py-8" data-testid="public-profile-card">
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-6 sm:p-8 shadow-sm text-center">
        {/* Symmetric Hero / Initials Monogram Badge */}
        <div
          className="mx-auto w-24 h-24 rounded-full bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-600 text-white font-bold text-3xl shadow-md ring-4 ring-indigo-500/10 dark:ring-indigo-400/20 flex items-center justify-center select-none"
          aria-hidden="true"
        >
          {initials}
        </div>

        {/* User Name */}
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mt-4 tracking-tight">
          {profile.name}
        </h2>

        {/* Role Pill */}
        <div className="mt-2.5 inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200/60 dark:border-indigo-800/60">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-600 dark:bg-indigo-400" />
          {roleDisplay}
        </div>

        {/* Symmetric Card Information Section */}
        <div className="mt-8 pt-6 border-t border-zinc-100 dark:border-zinc-800">
          <div className="p-4 rounded-2xl bg-zinc-50/70 dark:bg-zinc-800/40 border border-zinc-200/80 dark:border-zinc-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400 flex items-center justify-center shrink-0 border border-purple-200/40 dark:border-purple-900/40">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                  />
                </svg>
              </div>
              <div className="text-left">
                <span className="block text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                  Nexora Member
                </span>
                <span className="block text-sm font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">
                  Public Profile
                </span>
              </div>
            </div>

            <span className="text-xs font-mono px-2.5 py-1 rounded-lg bg-zinc-200/60 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
              #{profile.id}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
