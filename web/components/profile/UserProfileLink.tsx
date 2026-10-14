import React from 'react';
import Link from 'next/link';
import { parseUserId } from '@/lib/profile-utils';

export interface UserProfileLinkProps {
  userId: number | string;
  children?: React.ReactNode;
  className?: string;
  ariaLabel?: string;
  showIcon?: boolean;
}

/**
 * Reusable client-side link component to a user's safe public profile.
 * Validates the user ID before constructing the URL to prevent malformed routes.
 */
export function UserProfileLink({
  userId,
  children,
  className,
  ariaLabel,
  showIcon = false,
}: UserProfileLinkProps) {
  const validId = parseUserId(userId);

  // If user ID is invalid, safely render non-link fallback to avoid navigation to broken routes
  if (validId === null) {
    return (
      <span className={className || 'text-zinc-400 dark:text-zinc-500 cursor-not-allowed'}>
        {children || 'Unknown User'}
      </span>
    );
  }

  const href = `/users/${validId}`;
  const defaultLabel =
    typeof children === 'string'
      ? `View ${children}'s public profile`
      : `View user #${validId}'s public profile`;

  return (
    <Link
      href={href}
      className={
        className ||
        'inline-flex items-center gap-1.5 font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 hover:underline transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded'
      }
      aria-label={ariaLabel || defaultLabel}
    >
      {showIcon && (
        <svg
          className="w-4 h-4 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
          />
        </svg>
      )}
      {children || `User #${validId}`}
    </Link>
  );
}
