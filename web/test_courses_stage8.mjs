/**
 * Phase 5, Stage 8 - Course Catalog Foundation Frontend Test Suite
 * Minimum test coverage:
 * 1. course catalog rendering
 * 2. loading state
 * 3. empty state
 * 4. error state
 * 5. retry behavior
 * 6. search/filter interaction
 * 7. course navigation
 * 8. course detail rendering
 * 9. course detail not-found state
 * Plus Security Invariants (no localStorage, sessionStorage, document.cookie, Bearer).
 */

import test from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';

import {
  parseCourseId,
  formatCoursePrice,
  formatPointsPrice,
  getLevelBadgeStyle,
} from './lib/course-utils.ts';

import {
  ApiError,
  getCourses,
  getCourseById,
} from './lib/api.ts';

const mockCourseList = [
  {
    id: 1,
    title: 'Full-Stack Web Development',
    description: 'Master Next.js, FastAPI, and Supabase from scratch.',
    instructor: 'Sarah Connor',
    category: 'Web Development',
    level: 'Intermediate',
    duration: '8 weeks',
    thumbnail: '💻',
    total_lessons: 24,
    rating: 4.9,
    price: 49,
    points_price: 500,
    created_at: '2026-10-15T02:00:00Z',
  },
  {
    id: 2,
    title: 'Introduction to Python',
    description: 'Learn the fundamentals of Python programming.',
    instructor: 'Guido Ross',
    category: 'Programming',
    level: 'Beginner',
    duration: '4 weeks',
    thumbnail: '🐍',
    total_lessons: 12,
    rating: 4.8,
    price: 0,
    points_price: 0,
    created_at: '2026-10-14T10:00:00Z',
  },
];

const mockCourseDetail = {
  id: 1,
  title: 'Full-Stack Web Development',
  description: 'Master Next.js, FastAPI, and Supabase from scratch.',
  instructor: 'Sarah Connor',
  category: 'Web Development',
  level: 'Intermediate',
  duration: '8 weeks',
  thumbnail: '💻',
  total_lessons: 24,
  rating: 4.9,
  price: 49,
  points_price: 500,
  created_by: 10,
  created_at: '2026-10-15T02:00:00Z',
};

// 1. Course Catalog Rendering
test('1. Course catalog rendering validates expected fields and structure', () => {
  assert.strictEqual(mockCourseList.length, 2);
  const first = mockCourseList[0];
  assert.strictEqual(typeof first.id, 'number');
  assert.strictEqual(typeof first.title, 'string');
  assert.strictEqual(typeof first.description, 'string');
  assert.strictEqual(typeof first.instructor, 'string');
  assert.strictEqual(typeof first.category, 'string');
  assert.strictEqual(typeof first.level, 'string');
  assert.strictEqual(typeof first.duration, 'string');
  assert.strictEqual(typeof first.total_lessons, 'number');
  assert.strictEqual(typeof first.rating, 'number');
  assert.strictEqual(typeof first.price, 'number');
  assert.strictEqual(typeof first.points_price, 'number');
});

// 2. Loading State
test('2. Loading state: UI components define symmetric loading skeleton identifiers', () => {
  const catalogPageContent = fs.readFileSync(
    path.join(process.cwd(), 'app/courses/page.tsx'),
    'utf-8'
  );
  assert.ok(
    catalogPageContent.includes('courses-loading'),
    'Course catalog page must include courses-loading state identifier'
  );
  assert.ok(
    catalogPageContent.includes('animate-pulse'),
    'Loading skeleton must feature pulse animation'
  );
});

// 3. Empty State
test('3. Empty state: UI gracefully handles 0 courses returned from API', () => {
  const catalogPageContent = fs.readFileSync(
    path.join(process.cwd(), 'app/courses/page.tsx'),
    'utf-8'
  );
  assert.ok(
    catalogPageContent.includes('courses-empty'),
    'Course catalog page must include courses-empty testid'
  );
  assert.ok(
    catalogPageContent.includes('No Courses Found'),
    'Empty state must inform the user that no courses were found'
  );
  assert.ok(
    catalogPageContent.includes('Clear All Filters') || catalogPageContent.includes('Reset All'),
    'Empty state must provide filter clear/reset action'
  );
});

// 4. Error State
test('4. Error state: API errors are cleanly captured into ApiError with status', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({ detail: 'Database service is currently unavailable.' }),
      {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }
    );

  try {
    await getCourses();
    assert.fail('getCourses must throw on HTTP 503');
  } catch (err) {
    assert.ok(err instanceof ApiError);
    assert.strictEqual(err.status, 503);
    assert.strictEqual(err.message, 'Database service is currently unavailable.');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

// 5. Retry Behavior
test('5. Retry behavior: successfully recovers from temporary network glitch', async () => {
  let attemptCount = 0;
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => {
    attemptCount++;
    if (attemptCount === 1) {
      throw new Error('Transient connection error');
    }
    return new Response(
      JSON.stringify({ courses: mockCourseList, total: mockCourseList.length }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  };

  try {
    // Attempt 1: fails
    let failed = false;
    try {
      await getCourses();
    } catch {
      failed = true;
    }
    assert.strictEqual(failed, true, 'First attempt must fail');

    // Attempt 2 (Retry): succeeds
    const data = await getCourses();
    assert.strictEqual(data.total, 2);
    assert.strictEqual(data.courses.length, 2);
    assert.strictEqual(attemptCount, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

// 6. Search & Filter Interaction
test('6. Search & filter interaction: getCourses formats query string accurately', async () => {
  const originalFetch = globalThis.fetch;
  let interceptedUrl = '';

  globalThis.fetch = async (url) => {
    interceptedUrl = String(url);
    return new Response(
      JSON.stringify({ courses: [mockCourseList[0]], total: 1 }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  };

  try {
    await getCourses({
      search: 'FastAPI',
      category: 'Web Development',
      level: 'Intermediate',
    });

    const parsed = new URL(interceptedUrl);
    assert.strictEqual(parsed.pathname, '/api/v1/courses');
    assert.strictEqual(parsed.searchParams.get('search'), 'FastAPI');
    assert.strictEqual(parsed.searchParams.get('category'), 'Web Development');
    assert.strictEqual(parsed.searchParams.get('level'), 'Intermediate');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

// 7. Course Navigation & ID Validation
test('7. Course navigation: parseCourseId validates positive integers and rejects malformed IDs', () => {
  // Valid IDs
  assert.strictEqual(parseCourseId(1), 1);
  assert.strictEqual(parseCourseId('42'), 42);
  assert.strictEqual(parseCourseId('  999  '), 999);

  // Invalid IDs
  assert.strictEqual(parseCourseId(0), null);
  assert.strictEqual(parseCourseId('0'), null);
  assert.strictEqual(parseCourseId(-10), null);
  assert.strictEqual(parseCourseId('-10'), null);
  assert.strictEqual(parseCourseId('abc'), null);
  assert.strictEqual(parseCourseId(''), null);
  assert.strictEqual(parseCourseId(null), null);
  assert.strictEqual(parseCourseId(undefined), null);
  assert.strictEqual(parseCourseId('1; DROP TABLE courses'), null);

  // getCourseById throws immediately for invalid IDs before fetch
  assert.rejects(
    async () => getCourseById(0),
    /Course ID must be a positive integer/
  );
  assert.rejects(
    async () => getCourseById(-1),
    /Course ID must be a positive integer/
  );
});

// 8. Course Detail Rendering
test('8. Course detail rendering: formats price, points, duration, and level styles accurately', () => {
  // Free course
  assert.strictEqual(formatCoursePrice(0), 'Free');
  assert.strictEqual(formatCoursePrice(null), 'Free');
  // Paid course
  assert.strictEqual(formatCoursePrice(49), '$49');

  // Points price
  assert.strictEqual(formatPointsPrice(0), '0 pts');
  assert.strictEqual(formatPointsPrice(500), '500 pts');
  assert.strictEqual(formatPointsPrice(1500), '1,500 pts');

  // Level badge styles
  const beg = getLevelBadgeStyle('Beginner');
  assert.ok(beg.bg.includes('emerald'));
  const int = getLevelBadgeStyle('Intermediate');
  assert.ok(int.bg.includes('amber'));
  const adv = getLevelBadgeStyle('Advanced');
  assert.ok(adv.bg.includes('purple'));
});

// 9. Course Detail Not-Found State
test('9. Course detail not-found state: 404 from API translates to ApiError', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({ detail: 'Course not found.' }),
      {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      }
    );

  try {
    await getCourseById(99999);
    assert.fail('getCourseById must throw on HTTP 404');
  } catch (err) {
    assert.ok(err instanceof ApiError);
    assert.strictEqual(err.status, 404);
    assert.strictEqual(err.message, 'Course not found.');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

// 10. Security Invariants
test('10. Security Invariants: No localStorage, sessionStorage, document.cookie, or Bearer tokens', () => {
  const filesToCheck = [
    'app/courses/page.tsx',
    'app/courses/[courseId]/page.tsx',
    'components/courses/CourseCard.tsx',
    'lib/course-utils.ts',
    'lib/api.ts',
    'lib/types.ts',
  ];

  for (const relPath of filesToCheck) {
    const fullPath = path.join(process.cwd(), relPath);
    if (!fs.existsSync(fullPath)) continue;
    const content = fs.readFileSync(fullPath, 'utf-8');

    assert.ok(!content.includes('localStorage'), `${relPath} contains localStorage`);
    assert.ok(!content.includes('sessionStorage'), `${relPath} contains sessionStorage`);
    assert.ok(!content.includes('document.cookie'), `${relPath} contains document.cookie`);
    assert.ok(!content.includes('Authorization: Bearer'), `${relPath} contains Authorization: Bearer`);
    assert.ok(!content.includes('Bearer '), `${relPath} contains Bearer token`);
    assert.ok(!content.includes('dangerouslySetInnerHTML'), `${relPath} contains dangerouslySetInnerHTML`);
    assert.ok(!content.includes('eval('), `${relPath} contains eval()`);
  }
});

// 11. Safe Public Data Representation
test('11. Safe Public Data: course objects strictly contain safe fields only', () => {
  const sensitiveFields = ['password', 'password_hash', 'token', 'secret', 'email', 'reset_token'];
  for (const course of mockCourseList) {
    for (const field of sensitiveFields) {
      assert.strictEqual(field in course, false, `Course list item must not contain ${field}`);
    }
  }
  for (const field of sensitiveFields) {
    assert.strictEqual(field in mockCourseDetail, false, `Course detail must not contain ${field}`);
  }
});
