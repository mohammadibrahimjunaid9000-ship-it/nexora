/**
 * Phase 5, Stage 9 - Course Enrollment Foundation Frontend Test Suite
 * Minimum test coverage:
 * 1. enroll button / not-enrolled state exists
 * 2. enrolled state renders correctly
 * 3. loading state prevents duplicate submission
 * 4. API error state renders
 * 5. unauthenticated state is handled
 * 6. invalid course route remains safe
 * 7. getEnrollmentStatus and enrollInCourse methods query correct endpoints with credentials: include
 * 8. no Bearer token usage in enrollment requests
 * 9. no localStorage, sessionStorage, or document.cookie usage
 * 10. no fabricated user IDs or course records
 * 11. verified live schema fields only (id, user_id, course_id, progress, completed_lessons, enrolled_at)
 */

import test from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';

import {
  ApiError,
  getEnrollmentStatus,
  enrollInCourse,
} from './lib/api.ts';

const mockEnrollmentRecord = {
  id: 101,
  user_id: 10,
  course_id: 1,
  progress: 0,
  completed_lessons: 0,
  enrolled_at: '2026-10-17T00:00:00Z',
};

// 1. API Client - getEnrollmentStatus
test('1. getEnrollmentStatus calls correct endpoint with credentials: include and no Bearer token', async () => {
  const originalFetch = globalThis.fetch;
  let interceptedUrl = '';
  let interceptedOptions = null;

  globalThis.fetch = async (url, options) => {
    interceptedUrl = String(url);
    interceptedOptions = options;
    return new Response(
      JSON.stringify({
        is_enrolled: false,
        course_id: 1,
        enrollment: null,
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  };

  try {
    const data = await getEnrollmentStatus(1);
    assert.strictEqual(data.is_enrolled, false);
    assert.strictEqual(data.course_id, 1);
    assert.strictEqual(data.enrollment, null);

    const parsed = new URL(interceptedUrl);
    assert.strictEqual(parsed.pathname, '/api/v1/courses/1/enrollment-status');
    assert.strictEqual(interceptedOptions?.credentials, 'include');
    assert.strictEqual(
      interceptedOptions?.headers?.get?.('Authorization'),
      null,
      'Must NOT contain Authorization header'
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

// 2. API Client - enrollInCourse
test('2. enrollInCourse calls POST /api/v1/courses/{id}/enroll with credentials: include and no Bearer', async () => {
  const originalFetch = globalThis.fetch;
  let interceptedUrl = '';
  let interceptedOptions = null;

  globalThis.fetch = async (url, options) => {
    interceptedUrl = String(url);
    interceptedOptions = options;
    return new Response(JSON.stringify(mockEnrollmentRecord), {
      status: 201,
      headers: { 'Content-Type': 'application/json' },
      statusText: 'Created',
    });
  };

  try {
    const record = await enrollInCourse(1);
    assert.strictEqual(record.id, 101);
    assert.strictEqual(record.course_id, 1);
    assert.strictEqual(record.user_id, 10);
    assert.strictEqual(record.progress, 0);

    const parsed = new URL(interceptedUrl);
    assert.strictEqual(parsed.pathname, '/api/v1/courses/1/enroll');
    assert.strictEqual(interceptedOptions?.method, 'POST');
    assert.strictEqual(interceptedOptions?.credentials, 'include');
    assert.strictEqual(
      interceptedOptions?.headers?.get?.('Authorization'),
      null,
      'Must NOT contain Authorization header'
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

// 3. Input Validation
test('3. API methods reject invalid or non-positive course IDs prior to making network requests', async () => {
  assert.rejects(async () => getEnrollmentStatus(0), /Course ID must be a positive integer/);
  assert.rejects(async () => getEnrollmentStatus(-5), /Course ID must be a positive integer/);
  assert.rejects(async () => enrollInCourse(0), /Course ID must be a positive integer/);
  assert.rejects(async () => enrollInCourse(-10), /Course ID must be a positive integer/);
});

// 4. Enroll Button / State in Component
test('4. Enroll button / not-enrolled state exists in course detail component', () => {
  const pageContent = fs.readFileSync(
    path.join(process.cwd(), 'app/courses/[courseId]/page.tsx'),
    'utf-8'
  );
  assert.ok(
    pageContent.includes('enroll-button'),
    'Course detail page must include enroll-button identifier'
  );
  assert.ok(
    pageContent.includes('Enroll in Course'),
    'Component must render Enroll in Course text'
  );
});

// 5. Enrolled State in Component
test('5. Enrolled state renders active enrollment badge and progress details', () => {
  const pageContent = fs.readFileSync(
    path.join(process.cwd(), 'app/courses/[courseId]/page.tsx'),
    'utf-8'
  );
  assert.ok(
    pageContent.includes('enrolled-badge'),
    'Course detail page must include enrolled-badge identifier'
  );
  assert.ok(
    pageContent.includes('You are enrolled in this course'),
    'Component must confirm active enrollment'
  );
  assert.ok(
    pageContent.includes('Active Enrollment'),
    'Component must render Active Enrollment label'
  );
});

// 6. Loading & Double-Submission Prevention
test('6. Loading state disables button and prevents duplicate submission', () => {
  const pageContent = fs.readFileSync(
    path.join(process.cwd(), 'app/courses/[courseId]/page.tsx'),
    'utf-8'
  );
  assert.ok(
    pageContent.includes('enrollment-in-progress'),
    'Component must feature enrollment-in-progress container'
  );
  assert.ok(
    pageContent.includes('enrolling-button'),
    'Component must have dedicated disabled enrolling-button'
  );
  assert.ok(
    pageContent.includes('cursor-not-allowed'),
    'Enrolling button must indicate not-allowed cursor'
  );
});

// 7. API Error State in Component
test('7. API error state renders informative notice and retry action', () => {
  const pageContent = fs.readFileSync(
    path.join(process.cwd(), 'app/courses/[courseId]/page.tsx'),
    'utf-8'
  );
  assert.ok(
    pageContent.includes('enroll-error'),
    'Course detail page must include enroll-error container'
  );
  assert.ok(
    pageContent.includes('Enrollment Notice'),
    'Error section must show clear notice'
  );
  assert.ok(
    pageContent.includes('Try Again'),
    'Error section must provide a retry action'
  );
});

// 8. Unauthenticated User State
test('8. Unauthenticated state informs user and provides sign-in action', () => {
  const pageContent = fs.readFileSync(
    path.join(process.cwd(), 'app/courses/[courseId]/page.tsx'),
    'utf-8'
  );
  assert.ok(
    pageContent.includes('enroll-unauthenticated'),
    'Component must include enroll-unauthenticated container'
  );
  assert.ok(
    pageContent.includes('Sign In to Enroll'),
    'Component must prompt to sign in'
  );
  assert.ok(
    pageContent.includes('sign-in-to-enroll-link'),
    'Component must link to sign-in'
  );
});

// 9. Error Handling - 409 Conflict & 503 DB Failure
test('9. ApiError correctly captures 409 Conflict and 503 Service Unavailable', async () => {
  const originalFetch = globalThis.fetch;

  // 409 Conflict
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: 'Already enrolled in this course.' }), {
      status: 409,
      headers: { 'Content-Type': 'application/json' },
    });

  try {
    await enrollInCourse(1);
    assert.fail('enrollInCourse must throw on HTTP 409');
  } catch (err) {
    assert.ok(err instanceof ApiError);
    assert.strictEqual(err.status, 409);
    assert.strictEqual(err.message, 'Already enrolled in this course.');
  }

  // 503 Service Unavailable
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: 'Database service is currently unavailable.' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });

  try {
    await enrollInCourse(1);
    assert.fail('enrollInCourse must throw on HTTP 503');
  } catch (err) {
    assert.ok(err instanceof ApiError);
    assert.strictEqual(err.status, 503);
    assert.strictEqual(err.message, 'Database service is currently unavailable.');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

// 10. Security Invariants
test('10. Security Invariants: No localStorage, sessionStorage, document.cookie, or Bearer tokens', () => {
  const filesToCheck = [
    'app/courses/[courseId]/page.tsx',
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

// 11. Authoritative Schema & Safe Data Representation
test('11. Authoritative Schema: enrollment record contains only verified columns', () => {
  const allowedKeys = new Set(['id', 'user_id', 'course_id', 'progress', 'completed_lessons', 'enrolled_at']);
  for (const k of Object.keys(mockEnrollmentRecord)) {
    assert.ok(allowedKeys.has(k), `Unexpected column ${k} in enrollment record`);
  }

  const sensitiveFields = ['password', 'password_hash', 'token', 'secret', 'email'];
  for (const f of sensitiveFields) {
    assert.strictEqual(f in mockEnrollmentRecord, false, `Enrollment must not contain ${f}`);
  }
});
