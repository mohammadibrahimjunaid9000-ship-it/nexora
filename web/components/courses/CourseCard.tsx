import React from 'react';
import Link from 'next/link';
import type { CourseListItem } from '@/lib/types';
import { formatCoursePrice, formatPointsPrice, getLevelBadgeStyle } from '@/lib/course-utils';

interface CourseCardProps {
  course: CourseListItem;
}

export function CourseCard({ course }: CourseCardProps) {
  const levelStyle = getLevelBadgeStyle(course.level);
  const isFree = course.price === 0;

  return (
    <article
      data-testid={`course-card-${course.id}`}
      className="group relative flex flex-col justify-between rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/90 shadow-xs hover:shadow-lg hover:border-indigo-300 dark:hover:border-indigo-500/50 transition-all duration-300 overflow-hidden"
    >
      {/* Top Banner / Thumbnail Area */}
      <div className="relative w-full h-44 bg-gradient-to-br from-indigo-500/10 via-purple-500/10 to-pink-500/10 dark:from-indigo-950/40 dark:via-purple-950/40 dark:to-pink-950/40 flex items-center justify-center border-b border-zinc-100 dark:border-zinc-800/80 overflow-hidden">
        {/* Subtle decorative background circles */}
        <div className="absolute -top-12 -right-12 w-32 h-32 bg-indigo-500/10 dark:bg-indigo-500/20 rounded-full blur-xl pointer-events-none" />
        <div className="absolute -bottom-12 -left-12 w-32 h-32 bg-purple-500/10 dark:bg-purple-500/20 rounded-full blur-xl pointer-events-none" />

        {/* Thumbnail Emoji or Icon */}
        <div className="text-5xl select-none transform group-hover:scale-110 transition-transform duration-300">
          {course.thumbnail || '📚'}
        </div>

        {/* Category & Level Badges */}
        <div className="absolute top-3 left-3 right-3 flex items-center justify-between pointer-events-none">
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-white/90 dark:bg-zinc-900/90 text-indigo-700 dark:text-indigo-300 border border-indigo-100 dark:border-indigo-900/50 shadow-xs backdrop-blur-sm">
            {course.category}
          </span>
          <span
            className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border shadow-xs backdrop-blur-sm ${levelStyle.bg} ${levelStyle.text} ${levelStyle.border}`}
          >
            {course.level}
          </span>
        </div>
      </div>

      {/* Content Area */}
      <div className="p-5 flex-1 flex flex-col justify-between gap-4">
        <div className="space-y-2.5">
          {/* Metadata Row: Rating, Lessons, Duration */}
          <div className="flex items-center gap-3 text-xs text-zinc-500 dark:text-zinc-400">
            <span className="inline-flex items-center gap-1 font-semibold text-amber-600 dark:text-amber-400">
              <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 20 20" aria-hidden="true">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              {Number(course.rating).toFixed(1)}
            </span>
            <span>•</span>
            <span>{course.total_lessons} lessons</span>
            <span>•</span>
            <span>{course.duration}</span>
          </div>

          {/* Title */}
          <h3 className="font-bold text-lg text-zinc-900 dark:text-zinc-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors line-clamp-1">
            {course.title}
          </h3>

          {/* Description */}
          <p className="text-sm text-zinc-600 dark:text-zinc-400 line-clamp-2 leading-relaxed">
            {course.description}
          </p>
        </div>

        {/* Instructor */}
        <div className="pt-2 border-t border-zinc-100 dark:border-zinc-800/80 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white text-[10px] font-bold">
              {course.instructor.charAt(0).toUpperCase()}
            </div>
            <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300 truncate max-w-[140px]">
              {course.instructor}
            </span>
          </div>

          {/* Pricing Info */}
          <div className="text-right">
            <span className={`text-sm font-bold ${isFree ? 'text-emerald-600 dark:text-emerald-400' : 'text-zinc-900 dark:text-zinc-100'}`}>
              {formatCoursePrice(course.price)}
            </span>
            {course.points_price > 0 && (
              <span className="block text-[11px] text-zinc-500 dark:text-zinc-400">
                or {formatPointsPrice(course.points_price)}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Card Action Link */}
      <div className="px-5 pb-5">
        <Link
          href={`/courses/${course.id}`}
          className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-medium bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 shadow-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          aria-label={`View course: ${course.title}`}
        >
          <span>View Course</span>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </Link>
      </div>
    </article>
  );
}
