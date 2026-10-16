/**
 * Phase 5, Stage 10 - Learning Foundation Frontend Test Suite
 * Minimum test coverage:
 * 1. lessons section renders in course detail page
 * 2. loading state supported
 * 3. empty state supported
 * 4. error state supported
 * 5. retry mechanism supported
 * 6. lesson links use real dynamic IDs (no hardcoded/fake IDs)
 * 7. lesson detail page handles invalid IDs safely
 * 8. lesson detail page renders verified fields and back link
 * 9. getCourseLessons and getLessonById query correct endpoints with credentials: include
 * 10. no Bearer token authentication
 * 11. no localStorage, sessionStorage, or document.cookie usage
 * 12. no fabricated lesson records or fake lesson IDs
 * 13. only verified safe fields in TypeScript types (no invented fields)
 */

import test from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';

import {
  getCourseLessons,
  getLessonById,
} from './lib/api.ts';


const mockLessonItem = {
  id: 42,
  course_id: 1,
  title: 'Understanding Modern Web Architectures',
  description: 'An architectural deep dive into Next.js and FastAPI.',
};

// 1. API Client - getCourseLessons
test('1. getCourseLessons calls GET /api/v1/courses/{id}/lessons with credentials: include and no Bearer token', async () => {
  const originalFetch = globalThis.fetch;
  let interceptedUrl = '';
  let interceptedOptions = null;

  globalThis.fetch = async (url, options) => {
    interceptedUrl = String(url);
    interceptedOptions = options;
    return new Response(
      JSON.stringify({
        course_id: 1,
        lessons: [mockLessonItem],
        total: 1,
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  };

  try {
    const data = await getCourseLessons(1);
    assert.strictEqual(data.course_id, 1);
    assert.strictEqual(data.total, 1);
    assert.strictEqual(data.lessons.length, 1);
    assert.strictEqual(data.lessons[0].id, 42);

    const parsed = new URL(interceptedUrl);
    assert.strictEqual(parsed.pathname, '/api/v1/courses/1/lessons');
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

// 2. API Client - getCourseLessons input validation
test('2. getCourseLessons rejects invalid numeric course IDs', async () => {
  await assert.rejects(
    async () => {
      // @ts-expect-error Testing runtime invalid input
      await getCourseLessons('invalid-id');
    },
    {
      message: 'Course ID must be a positive integer.',
    }
  );

  await assert.rejects(
    async () => {
      await getCourseLessons(0);
    },
    {
      message: 'Course ID must be a positive integer.',
    }
  );

  await assert.rejects(
    async () => {
      await getCourseLessons(-5);
    },
    {
      message: 'Course ID must be a positive integer.',
    }
  );
});

// 3. API Client - getLessonById
test('3. getLessonById calls /api/v1/courses/{cid}/lessons/{lid} with credentials: include and no Bearer', async () => {
  const originalFetch = globalThis.fetch;
  let interceptedUrl = '';
  let interceptedOptions = null;

  globalThis.fetch = async (url, options) => {
    interceptedUrl = String(url);
    interceptedOptions = options;
    return new Response(JSON.stringify(mockLessonItem), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  try {
    const data = await getLessonById(1, 42);
    assert.strictEqual(data.id, 42);
    assert.strictEqual(data.course_id, 1);
    assert.strictEqual(data.title, 'Understanding Modern Web Architectures');

    const parsed = new URL(interceptedUrl);
    assert.strictEqual(parsed.pathname, '/api/v1/courses/1/lessons/42');
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

// 4. API Client - getLessonById rejects invalid course IDs
test('4. getLessonById rejects invalid numeric course IDs', async () => {
  await assert.rejects(
    async () => {
      // @ts-expect-error Testing runtime invalid input
      await getLessonById('invalid-cid', 42);
    },
    {
      message: 'Course ID must be a positive integer.',
    }
  );

  await assert.rejects(
    async () => {
      await getLessonById(0, 42);
    },
    {
      message: 'Course ID must be a positive integer.',
    }
  );

  await assert.rejects(
    async () => {
      await getLessonById(-5, 42);
    },
    {
      message: 'Course ID must be a positive integer.',
    }
  );
});

// 5. API Client - getLessonById input validation
test('5. getLessonById rejects invalid numeric lesson IDs', async () => {
  await assert.rejects(
    async () => {
      // @ts-expect-error Testing runtime invalid input
      await getLessonById(1, 'abc');
    },
    {
      message: 'Lesson ID must be a positive integer.',
    }
  );

  await assert.rejects(
    async () => {
      await getLessonById(1, 0);
    },
    {
      message: 'Lesson ID must be a positive integer.',
    }
  );

  await assert.rejects(
    async () => {
      await getLessonById(1, -10);
    },
    {
      message: 'Lesson ID must be a positive integer.',
    }
  );
});


// 6. UI Structure - Course Detail Page Lessons Section
test('6. Course detail page contains lessons curriculum section with all required states and testids', () => {
  const filePath = path.resolve('app/courses/[courseId]/page.tsx');
  const code = fs.readFileSync(filePath, 'utf-8');

  // Lessons section
  assert.match(code, /data-testid="lessons-section"/, 'Must contain lessons-section');
  assert.match(code, /Course Curriculum/, 'Must have Course Curriculum heading');

  // Loading state
  assert.match(code, /data-testid="lessons-loading"/, 'Must contain lessons-loading');

  // Empty state
  assert.match(code, /data-testid="lessons-empty"/, 'Must contain lessons-empty');
  assert.match(code, /No Lessons Available Yet/, 'Must have empty state copy');

  // Error state and retry
  assert.match(code, /data-testid="lessons-error"/, 'Must contain lessons-error');
  assert.match(code, /data-testid="lessons-retry-button"/, 'Must contain lessons-retry-button');
  assert.match(code, /handleRetryLessons/, 'Must have handleRetryLessons handler');

  // Lessons list state and real IDs
  assert.match(code, /data-testid="lessons-list"/, 'Must contain lessons-list');
  assert.match(code, /lesson-item-\$\{lesson\.id\}/, 'Must use dynamic lesson ID for lesson item');
  assert.match(code, /lesson-link-\$\{lesson\.id\}/, 'Must use dynamic lesson ID for lesson link');
  assert.match(
    code,
    /\/courses\/\$\{course\.id\}\/lessons\/\$\{lesson\.id\}/,
    'Must link to real lesson detail route'
  );
});

// 7. UI Structure - Lesson Detail Page
test('7. Lesson detail page exists and implements loading, 404, error, retry, and back link', () => {
  const filePath = path.resolve('app/courses/[courseId]/lessons/[lessonId]/page.tsx');
  assert.ok(fs.existsSync(filePath), 'Lesson detail page file must exist');

  const code = fs.readFileSync(filePath, 'utf-8');

  // Component structure
  assert.match(code, /'use client'/, 'Must be a client component');
  assert.match(code, /use\(params\)/, 'Must resolve params using React use() hook');

  // States & testids
  assert.match(code, /data-testid="lesson-loading"/, 'Must contain lesson-loading');
  assert.match(code, /data-testid="lesson-not-found"/, 'Must contain lesson-not-found');
  assert.match(code, /data-testid="lesson-error-state"/, 'Must contain lesson-error-state');
  assert.match(code, /data-testid="lesson-retry-button"/, 'Must contain lesson-retry-button');
  assert.match(code, /data-testid="lesson-detail-view"/, 'Must contain lesson-detail-view');
  assert.match(code, /data-testid="lesson-title"/, 'Must contain lesson-title');
  assert.match(code, /data-testid="lesson-description"/, 'Must contain lesson-description');
  assert.match(code, /data-testid="back-to-course-link"/, 'Must contain back-to-course-link');
  assert.match(code, /data-testid="back-to-course-button"/, 'Must contain back-to-course-button');

  // Safe ID parsing
  assert.match(code, /parseCourseId\(rawCourseId\)/, 'Must validate course ID');
  assert.match(code, /parseCourseId\(rawLessonId\)/, 'Must validate lesson ID');
});

// 8. Security Audit - No localStorage, sessionStorage, or document.cookie
test('8. Strict Security Audit: No client storage or Bearer auth across Stage 10 frontend files', () => {
  const filesToCheck = [
    'app/courses/[courseId]/page.tsx',
    'app/courses/[courseId]/lessons/[lessonId]/page.tsx',
    'lib/api.ts',
    'lib/types.ts',
  ];

  const prohibitedPatterns = [
    { pattern: /\blocalStorage\b/, name: 'localStorage' },
    { pattern: /\bsessionStorage\b/, name: 'sessionStorage' },
    { pattern: /\bdocument\.cookie\b/, name: 'document.cookie' },
    { pattern: /\bBearer\b/, name: 'Bearer' },
    { pattern: /\bdangerouslySetInnerHTML\b/, name: 'dangerouslySetInnerHTML' },
    { pattern: /\beval\(/, name: 'eval' },
  ];

  for (const relativePath of filesToCheck) {
    const fullPath = path.resolve(relativePath);
    if (!fs.existsSync(fullPath)) continue;
    const content = fs.readFileSync(fullPath, 'utf-8');

    for (const { pattern, name } of prohibitedPatterns) {
      assert.strictEqual(
        pattern.test(content),
        false,
        `Prohibited pattern '${name}' detected in ${relativePath}`
      );
    }
  }
});

// 9. No Fabricated Records or Fake IDs
test('9. No fabricated lesson records or hardcoded fake IDs in frontend files', () => {
  const filesToCheck = [
    'app/courses/[courseId]/page.tsx',
    'app/courses/[courseId]/lessons/[lessonId]/page.tsx',
  ];

  for (const relativePath of filesToCheck) {
    const fullPath = path.resolve(relativePath);
    const content = fs.readFileSync(fullPath, 'utf-8');

    // Ensure no hardcoded dummy lesson lists
    assert.strictEqual(
      /lessons\s*=\s*\[\s*\{\s*id\s*:\s*\d+/.test(content),
      false,
      `Hardcoded lesson array detected in ${relativePath}`
    );
    assert.strictEqual(
      /mockLesson/i.test(content),
      false,
      `Mock lesson detected in production code ${relativePath}`
    );
    assert.strictEqual(
      /fakeLesson/i.test(content),
      false,
      `Fake lesson detected in production code ${relativePath}`
    );
  }
});

// 10. Type Safety - Types contain only verified safe fields
test('10. Type definitions in web/lib/types.ts contain only verified safe fields', () => {
  const typesPath = path.resolve('lib/types.ts');
  const content = fs.readFileSync(typesPath, 'utf-8');

  // Verify LessonItem & LessonDetail presence
  assert.match(content, /export interface LessonItem/, 'Must declare LessonItem');
  assert.match(content, /export interface LessonDetail/, 'Must declare LessonDetail');
  assert.match(content, /export interface CourseLessonsResponse/, 'Must declare CourseLessonsResponse');

  // Verify NO invented fields in LessonItem
  const inventedFields = [
    'video_url',
    'content',
    'duration',
    'is_completed',
    'progress_percentage',
    'completed_at',
  ];

  for (const field of inventedFields) {
    // Check if field is present in LessonItem or LessonDetail definition block
    const lessonItemMatch = content.match(/export interface LessonItem\s*\{([^}]+)\}/);
    if (lessonItemMatch) {
      assert.strictEqual(
        lessonItemMatch[1].includes(field),
        false,
        `Invented field '${field}' found in LessonItem type`
      );
    }

    const lessonDetailMatch = content.match(/export interface LessonDetail\s*\{([^}]+)\}/);
    if (lessonDetailMatch) {
      assert.strictEqual(
        lessonDetailMatch[1].includes(field),
        false,
        `Invented field '${field}' found in LessonDetail type`
      );
    }
  }
});
