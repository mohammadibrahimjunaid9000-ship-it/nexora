'use client';

import React, { useState } from 'react';
import { validateProfileName } from '@/lib/profile-utils';

export { validateProfileName };

interface ProfileEditFormProps {
  currentName: string;
  onSave: (newName: string) => Promise<void>;
  onCancel: () => void;
  isSaving: boolean;
  serverError: string | null;
}

export function ProfileEditForm({
  currentName,
  onSave,
  onCancel,
  isSaving,
  serverError,
}: ProfileEditFormProps) {
  const [name, setName] = useState(currentName);
  const [clientError, setClientError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSaving) return;

    const trimmed = name.trim();
    const validationError = validateProfileName(trimmed);
    if (validationError) {
      setClientError(validationError);
      return;
    }

    setClientError(null);
    await onSave(trimmed);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setName(e.target.value);
    if (clientError) {
      // Re-validate dynamically once user starts fixing it
      const err = validateProfileName(e.target.value);
      setClientError(err);
    }
  };

  const displayError = clientError || serverError;

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-zinc-50/60 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 mt-6 transition-all"
      data-testid="profile-edit-form"
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
          Edit Display Name
        </h3>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          {name.trim().length} / 150 characters
        </span>
      </div>

      <div className="space-y-3">
        <div>
          <label
            htmlFor="profile-name-input"
            className="block text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-1.5"
          >
            Full Name
          </label>
          <input
            id="profile-name-input"
            type="text"
            value={name}
            onChange={handleChange}
            disabled={isSaving}
            maxLength={160}
            required
            autoFocus
            autoComplete="name"
            spellCheck={false}
            aria-invalid={!!displayError}
            aria-describedby={displayError ? 'profile-name-error' : undefined}
            className="w-full px-4 py-2.5 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus-visible:ring-2 focus-visible:ring-indigo-500 focus:border-transparent transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
            placeholder="Enter your full name"
          />
        </div>

        {displayError && (
          <div
            id="profile-name-error"
            role="alert"
            aria-live="assertive"
            className="flex items-start gap-2 p-3 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/50 text-red-700 dark:text-red-300 text-xs"
          >
            <svg
              className="w-4 h-4 mt-0.5 shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span>{displayError}</span>
          </div>
        )}
      </div>

      {/* Symmetrical Button Row */}
      <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-zinc-200/80 dark:border-zinc-700/80">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSaving}
          className="px-4 py-2 rounded-xl text-sm font-medium border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 bg-white dark:bg-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-zinc-400"
        >
          Cancel
        </button>

        <button
          type="submit"
          disabled={isSaving || (clientError !== null && clientError !== undefined)}
          aria-busy={isSaving}
          className="inline-flex items-center justify-center px-5 py-2 rounded-xl text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-indigo-500"
        >
          {isSaving ? (
            <>
              <svg
                className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
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
              Saving...
            </>
          ) : (
            'Save Changes'
          )}
        </button>
      </div>
    </form>
  );
}
