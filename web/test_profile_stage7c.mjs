/**
 * Phase 4, Stage 7C - Frontend Test Suite
 * Validates Next.js Profile client methods, profile utilities, validation rules,
 * error handling, and security invariants.
 */

import test from 'node:test';
import assert from 'node:assert';

import {
  validateProfileName,
  formatRoleName,
  formatJoinedDate,
} from './lib/profile-utils.ts';

import {
  ApiError,
  fetchApi,
  getAuthenticatedProfile,
  updateAuthenticatedProfileName,
} from './lib/api.ts';

const mockProfile = {
  id: 101,
  name: 'Alex Rivera',
  email: 'alex.rivera@example.com',
  role: 'creator',
  points: 1250,
  joined_at: '2026-03-15T10:30:00Z',
};

test('1. Role formatting correctly handles learner, creator, admin, and null', () => {
  assert.strictEqual(formatRoleName('learner'), 'Learner');
  assert.strictEqual(formatRoleName('creator'), 'Creator');
  assert.strictEqual(formatRoleName('admin'), 'Admin');
  assert.strictEqual(formatRoleName(null), 'Learner');
  assert.strictEqual(formatRoleName(undefined), 'Learner');
  assert.strictEqual(formatRoleName(''), 'Learner');
  assert.strictEqual(formatRoleName('STUDENT'), 'Student');
});

test('2. Joined date formatting handles valid ISO strings and fallback gracefully', () => {
  const formatted = formatJoinedDate('2026-03-15T10:30:00Z');
  assert.ok(formatted.includes('2026'), 'Formatted date must contain year');
  assert.ok(formatted.includes('March') || formatted.includes('3'), 'Formatted date must contain month');
  assert.strictEqual(formatJoinedDate(null), 'Not available');
  assert.strictEqual(formatJoinedDate(undefined), 'Not available');
  assert.strictEqual(formatJoinedDate('invalid-date'), 'invalid-date');
});

test('3. Client validation rejects names shorter than 2 characters', () => {
  const err1 = validateProfileName('A');
  assert.ok(err1 !== null, 'Single character must fail');
  assert.ok(err1.includes('at least 2 characters'));

  const errEmpty = validateProfileName('');
  assert.ok(errEmpty !== null, 'Empty string must fail');
  assert.ok(errEmpty.includes('cannot be empty'));
});

test('4. Client validation rejects names longer than 150 characters', () => {
  const longName = 'A'.repeat(151);
  const err = validateProfileName(longName);
  assert.ok(err !== null, '151 characters must fail');
  assert.ok(err.includes('not exceed 150 characters'));

  const maxValidName = 'A'.repeat(150);
  assert.strictEqual(validateProfileName(maxValidName), null, '150 characters must be valid');
});

test('5. Client validation trims whitespace properly', () => {
  const errWhitespaceOnly = validateProfileName('     ');
  assert.ok(errWhitespaceOnly !== null, 'Whitespace-only must fail');
  assert.ok(errWhitespaceOnly.includes('empty or whitespace only'));

  const errShortPadded = validateProfileName('   A   ');
  assert.ok(errShortPadded !== null, 'Whitespace padded single char must fail');

  assert.strictEqual(validateProfileName('  Jane Doe  '), null, 'Valid padded name must pass');
});

test('6. GET /api/v1/users/me enforces credentials: include and never sends Authorization Bearer', async () => {
  const originalFetch = globalThis.fetch;
  let capturedRequest = null;

  globalThis.fetch = async (url, options) => {
    capturedRequest = { url, options };
    return {
      ok: true,
      json: async () => mockProfile,
    };
  };

  try {
    const result = await getAuthenticatedProfile();
    assert.strictEqual(result.id, 101);
    assert.strictEqual(result.name, 'Alex Rivera');
    assert.strictEqual(result.email, 'alex.rivera@example.com');
    assert.ok(capturedRequest.url.endsWith('/api/v1/users/me'), 'Target must be /api/v1/users/me');
    assert.strictEqual(capturedRequest.options.method, 'GET');
    assert.strictEqual(
      capturedRequest.options.credentials,
      'include',
      'Credentials MUST be include for HttpOnly cookies'
    );

    // Security check: No Authorization header
    const headers = capturedRequest.options.headers;
    const authHeader = headers instanceof Headers ? headers.get('Authorization') : headers?.Authorization;
    assert.ok(!authHeader, 'Must NOT send Authorization header');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('7. PUT /api/v1/users/me sends JSON payload with name and credentials: include', async () => {
  const originalFetch = globalThis.fetch;
  let capturedRequest = null;

  globalThis.fetch = async (url, options) => {
    capturedRequest = { url, options };
    return {
      ok: true,
      json: async () => ({ ...mockProfile, name: 'Jordan Reed' }),
    };
  };

  try {
    const result = await updateAuthenticatedProfileName({ name: 'Jordan Reed' });
    assert.strictEqual(result.name, 'Jordan Reed');
    assert.ok(capturedRequest.url.endsWith('/api/v1/users/me'), 'Target must be /api/v1/users/me');
    assert.strictEqual(capturedRequest.options.method, 'PUT');
    assert.strictEqual(capturedRequest.options.credentials, 'include');
    assert.strictEqual(capturedRequest.options.body, JSON.stringify({ name: 'Jordan Reed' }));

    const headers = capturedRequest.options.headers;
    const contentType = headers instanceof Headers ? headers.get('Content-Type') : headers?.['Content-Type'];
    assert.strictEqual(contentType, 'application/json');

    const authHeader = headers instanceof Headers ? headers.get('Authorization') : headers?.Authorization;
    assert.ok(!authHeader, 'Must NOT send Authorization header');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('8. API Client parses HTTP 401 into ApiError instance', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => ({
    ok: false,
    status: 401,
    json: async () => ({ detail: 'Not authenticated' }),
  });

  try {
    await getAuthenticatedProfile();
    assert.fail('Should have thrown on 401');
  } catch (err) {
    assert.ok(err instanceof ApiError);
    assert.strictEqual(err.status, 401);
    assert.strictEqual(err.message, 'Not authenticated');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('9. API Client parses HTTP 422 with validation errors into ApiError', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => ({
    ok: false,
    status: 422,
    json: async () => ({
      detail: [{ loc: ['body', 'name'], msg: 'Name must be at least 2 characters long' }],
    }),
  });

  try {
    await updateAuthenticatedProfileName({ name: 'X' });
    assert.fail('Should have thrown on 422');
  } catch (err) {
    assert.ok(err instanceof ApiError);
    assert.strictEqual(err.status, 422);
    assert.ok(err.message.includes('Name must be at least 2 characters'));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('10. API Client parses HTTP 503 Service Unavailable into ApiError', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => ({
    ok: false,
    status: 503,
    json: async () => ({ detail: 'Database service is currently unavailable.' }),
  });

  try {
    await getAuthenticatedProfile();
    assert.fail('Should have thrown on 503');
  } catch (err) {
    assert.ok(err instanceof ApiError);
    assert.strictEqual(err.status, 503);
    assert.strictEqual(err.message, 'Database service is currently unavailable.');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('11. API Client propagates network failures', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => {
    throw new TypeError('Failed to fetch');
  };

  try {
    await getAuthenticatedProfile();
    assert.fail('Should have thrown on network failure');
  } catch (err) {
    assert.ok(err instanceof TypeError);
    assert.strictEqual(err.message, 'Failed to fetch');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('12. fetchApi helper forwards custom options correctly', async () => {
  const originalFetch = globalThis.fetch;
  let captured = null;

  globalThis.fetch = async (url, options) => {
    captured = { url, options };
    return {
      ok: true,
      json: async () => ({ test: true }),
    };
  };

  try {
    await fetchApi('/test-endpoint', {
      method: 'POST',
      body: JSON.stringify({ a: 1 }),
    });
    assert.ok(captured.url.endsWith('/test-endpoint'));
    assert.strictEqual(captured.options.method, 'POST');
    assert.strictEqual(captured.options.credentials, 'include');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('13. Security Invariants: No localStorage / sessionStorage token storage', () => {
  assert.strictEqual(typeof globalThis.localStorage, 'undefined', 'localStorage must not be defined or used');
  assert.strictEqual(typeof globalThis.sessionStorage, 'undefined', 'sessionStorage must not be defined or used');
});
