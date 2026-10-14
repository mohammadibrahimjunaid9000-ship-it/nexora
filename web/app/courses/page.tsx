'use client';

import React, { useState, useEffect, useCallback, useTransition } from 'react';
import { CourseCard } from '@/components/courses/CourseCard';
import type { CourseListItem } from '@/lib/types';
import { ApiError, getCourses } from '@/lib/api';

const CATEGORIES = [
  'All Categories',
  'Web Development',
  'Programming',
  'Data Science',
  'AI & Machine Learning',
  'Design',
  'Business',
];

const LEVELS = [
  'All Levels',
  'Beginner',
  'Intermediate',
  'Advanced',
];

type FetchState =
  | { type: 'loading' }
  | { type: 'error'; message: string }
  | { type: 'success'; courses: CourseListItem[]; total: number };

export default function CourseCatalogPage() {
  const [search, setSearch] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [category, setCategory] = useState<string>('All Categories');
  const [level, setLevel] = useState<string>('All Levels');

  const [state, setState] = useState<FetchState>({ type: 'loading' });
  const [isPending, startTransition] = useTransition();

  // Debounce search input by 300ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Load courses whenever search, category, or level changes
  const loadCourses = useCallback(async () => {
    setState({ type: 'loading' });

    try {
      const catParam = category !== 'All Categories' ? category : undefined;
      const lvlParam = level !== 'All Levels' ? level : undefined;
      const searchParam = debouncedSearch.trim() || undefined;

      const data = await getCourses({
        search: searchParam,
        category: catParam,
        level: lvlParam,
      });

      startTransition(() => {
        setState({
          type: 'success',
          courses: data.courses,
          total: data.total,
        });
      });
    } catch (err: unknown) {
      startTransition(() => {
        if (err instanceof ApiError) {
          setState({
            type: 'error',
            message: err.message || `Unable to load courses (HTTP ${err.status}).`,
          });
        } else if (err instanceof Error) {
          setState({
            type: 'error',
            message: err.message || 'Network connection failed. Please verify your connection.',
          });
        } else {
          setState({
            type: 'error',
            message: 'An unexpected error occurred while loading courses.',
          });
        }
      });
    }
  }, [debouncedSearch, category, level]);

  useEffect(() => {
    loadCourses();
  }, [loadCourses]);

  const handleResetFilters = () => {
    setSearch('');
    setDebouncedSearch('');
    setCategory('All Categories');
    setLevel('All Levels');
  };

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header Section */}
        <section className="text-center space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200/80 dark:border-indigo-800/80 shadow-xs">
            <span>Explore Knowledge</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-zinc-900 dark:text-zinc-100">
            Course Catalog
          </h1>
          <p className="max-w-2xl mx-auto text-base text-zinc-600 dark:text-zinc-400">
            Discover in-depth courses crafted by industry creators. Master new skills at your own pace with practical hands-on learning.
          </p>
        </section>

        {/* Search & Filter Controls (Symmetric Bar) */}
        <section
          aria-label="Filter courses"
          className="rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/90 p-4 sm:p-5 shadow-xs space-y-4"
        >
          <div className="grid grid-cols-1 md:grid-cols-12 gap-3 sm:gap-4 items-center">
            {/* Search Input */}
            <div className="relative md:col-span-6">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-zinc-400">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <input
                id="search-input"
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by title or description..."
                className="w-full pl-10 pr-9 py-2.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all"
                aria-label="Search courses"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch('')}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
                  aria-label="Clear search"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>

            {/* Category Selector */}
            <div className="md:col-span-3">
              <label htmlFor="category-select" className="sr-only">
                Filter by Category
              </label>
              <select
                id="category-select"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full py-2.5 px-3 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all cursor-pointer"
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            {/* Level Selector */}
            <div className="md:col-span-3">
              <label htmlFor="level-select" className="sr-only">
                Filter by Level
              </label>
              <select
                id="level-select"
                value={level}
                onChange={(e) => setLevel(e.target.value)}
                className="w-full py-2.5 px-3 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all cursor-pointer"
              >
                {LEVELS.map((lvl) => (
                  <option key={lvl} value={lvl}>
                    {lvl}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Active Filter Indicators & Reset Action */}
          {(search || category !== 'All Categories' || level !== 'All Levels') && (
            <div className="flex items-center justify-between pt-2 border-t border-zinc-100 dark:border-zinc-800/80 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-zinc-500 dark:text-zinc-400">Active filters:</span>
                {search && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-medium">
                    Search: &ldquo;{search}&rdquo;
                  </span>
                )}
                {category !== 'All Categories' && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 font-medium">
                    {category}
                  </span>
                )}
                {level !== 'All Levels' && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 font-medium">
                    {level}
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={handleResetFilters}
                className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
              >
                Reset All
              </button>
            </div>
          )}
        </section>

        {/* Content Area States */}
        {state.type === 'loading' && (
          <section
            data-testid="courses-loading"
            aria-label="Loading courses"
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
          >
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div
                key={i}
                className="rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/90 p-5 space-y-4 animate-pulse"
              >
                <div className="w-full h-40 bg-zinc-200 dark:bg-zinc-800 rounded-xl" />
                <div className="h-4 bg-zinc-200 dark:bg-zinc-800 rounded w-1/3" />
                <div className="h-6 bg-zinc-200 dark:bg-zinc-800 rounded w-4/5" />
                <div className="h-4 bg-zinc-200 dark:bg-zinc-800 rounded w-full" />
                <div className="h-4 bg-zinc-200 dark:bg-zinc-800 rounded w-2/3" />
                <div className="h-10 bg-zinc-200 dark:bg-zinc-800 rounded-xl w-full" />
              </div>
            ))}
          </section>
        )}

        {state.type === 'error' && (
          <section
            data-testid="courses-error"
            className="rounded-2xl border border-red-200 dark:border-red-900/50 bg-red-50/50 dark:bg-red-950/20 p-8 text-center space-y-4 max-w-lg mx-auto"
          >
            <div className="w-12 h-12 mx-auto rounded-full bg-red-100 dark:bg-red-900/50 flex items-center justify-center text-red-600 dark:text-red-400">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div className="space-y-1">
              <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
                Failed to Load Courses
              </h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                {state.message}
              </p>
            </div>
            <button
              type="button"
              onClick={() => loadCourses()}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 shadow-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Try Again</span>
            </button>
          </section>
        )}

        {state.type === 'success' && state.courses.length === 0 && (
          <section
            data-testid="courses-empty"
            className="rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/90 p-10 text-center space-y-4 max-w-md mx-auto"
          >
            <div className="w-16 h-16 mx-auto rounded-2xl bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-3xl select-none">
              🔍
            </div>
            <div className="space-y-1">
              <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
                No Courses Found
              </h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                We couldn&apos;t find any courses matching your current filters. Try refining your search query or clearing your filter selections.
              </p>
            </div>
            {(search || category !== 'All Categories' || level !== 'All Levels') && (
              <button
                type="button"
                onClick={handleResetFilters}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
              >
                Clear All Filters
              </button>
            )}
          </section>
        )}

        {state.type === 'success' && state.courses.length > 0 && (
          <section aria-label="Course list" className="space-y-4">
            <div className="flex items-center justify-between text-sm text-zinc-500 dark:text-zinc-400">
              <span>Showing {state.courses.length} course{state.courses.length !== 1 ? 's' : ''}</span>
              {isPending && <span className="text-xs text-indigo-500 animate-pulse">Updating...</span>}
            </div>

            <div
              data-testid="courses-grid"
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
            >
              {state.courses.map((course) => (
                <CourseCard key={course.id} course={course} />
              ))}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
