/**
 * Phase 4, Stage 7D - Public Profile Frontend Test Suite
 * Validates public profile types, client methods, user ID sanitization,
 * role formatting, initials generation, error handling, and security invariants.
 */

import test from 'node:test';
import assert from 'node:assert';

import {
  parseUserId,
  getInitials,
  formatRoleName,
} from './lib/profile-utils.ts';

import {
  ApiError,
  getPublicUserProfile,
} from './lib/api.ts';

const mockPublicProfile = {
  id: 123,
  name: 'Mohammed Ibrahim',
  role: 'learner',
};

test('1. parseUserId correctly parses valid positive integer IDs', () => {
  assert.strictEqual(parseUserId('123'), 123);
  assert.strictEqual(parseUserId(42), 42);
  assert.strictEqual(parseUserId('1'), 1);
  assert.strictEqual(parseUserId('999999'), 999999);
  assert.strictEqual(parseUserId('  50  '), 50);
});

test('2. parseUserId safely rejects invalid, non-positive, or malformed inputs', () => {
  assert.strictEqual(parseUserId('abc'), null, 'String letters must return null');
  assert.strictEqual(parseUserId('0'), null, 'Zero must return null');
  assert.strictEqual(parseUserId(0), null, 'Zero numeric must return null');
  assert.strictEqual(parseUserId('-1'), null, 'Negative string must return null');
  assert.strictEqual(parseUserId(-1), null, 'Negative numeric must return null');
  assert.strictEqual(parseUserId('1.5'), null, 'Float string must return null');
  assert.strictEqual(parseUserId(1.5), null, 'Float numeric must return null');
  assert.strictEqual(parseUserId(''), null, 'Empty string must return null');
  assert.strictEqual(parseUserId('   '), null, 'Whitespace string must return null');
  assert.strictEqual(parseUserId(null), null, 'Null must return null');
  assert.strictEqual(parseUserId(undefined), null, 'Undefined must return null');
  assert.strictEqual(parseUserId('123/evil'), null, 'Path traversal attempt must return null');
  assert.strictEqual(parseUserId('1; DROP TABLE users'), null, 'SQL injection attempt must return null');
});

test('3. getInitials generates deterministic fallback initials without external services', () => {
  assert.strictEqual(getInitials('Mohammed Ibrahim'), 'MI');
  assert.strictEqual(getInitials('Alex Rivera'), 'AR');
  assert.strictEqual(getInitials('John'), 'JO');
  assert.strictEqual(getInitials('A'), 'A');
  assert.strictEqual(getInitials(''), 'U');
  assert.strictEqual(getInitials(null), 'U');
  assert.strictEqual(getInitials(undefined), 'U');
  assert.strictEqual(getInitials('First Middle Last'), 'FL');
});

test('4. formatRoleName accurately maps role strings for public display', () => {
  assert.strictEqual(formatRoleName('learner'), 'Learner');
  assert.strictEqual(formatRoleName('creator'), 'Creator');
  assert.strictEqual(formatRoleName('admin'), 'Admin');
  assert.strictEqual(formatRoleName(null), 'Learner');
  assert.strictEqual(formatRoleName(undefined), 'Learner');
  assert.strictEqual(formatRoleName(''), 'Learner');
});

test('5. getPublicUserProfile rejects invalid user IDs prior to making network requests', async () => {
  await assert.rejects(
    async () => getPublicUserProfile(0),
    /User ID must be a positive integer/
  );
  await assert.rejects(
    async () => getPublicUserProfile(-10),
    /User ID must be a positive integer/
  );
  await assert.rejects(
    async () => getPublicUserProfile(1.5),
    /User ID must be a positive integer/
  );
  await assert.rejects(
    // @ts-expect-error - testing invalid runtime input
    async () => getPublicUserProfile('abc'),
    /User ID must be a positive integer/
  );
});

test('6. getPublicUserProfile calls GET /api/v1/users/{id} without Authorization header', async () => {
  const originalFetch = globalThis.fetch;
  let captured = null;

  globalThis.fetch = async (url, options) => {
    captured = { url, options };
    return {
      ok: true,
      json: async () => mockPublicProfile,
    };
  };

  try {
    const profile = await getPublicUserProfile(123);
    assert.strictEqual(profile.id, 123);
    assert.strictEqual(profile.name, 'Mohammed Ibrahim');
    assert.strictEqual(profile.role, 'learner');

    assert.ok(captured.url.endsWith('/api/v1/users/123'), 'URL must end with /api/v1/users/123');
    assert.strictEqual(captured.options.method, 'GET');

    // Security check: No Authorization header
    const headers = captured.options.headers;
    const authHeader = headers instanceof Headers ? headers.get('Authorization') : headers?.Authorization;
    assert.ok(!authHeader, 'Must NOT send Authorization header');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('7. Only public fields exist on the returned profile (no private data)', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => ({
    ok: true,
    json: async () => mockPublicProfile,
  });

  try {
    const profile = await getPublicUserProfile(123);
    const keys = Object.keys(profile);
    assert.deepStrictEqual(keys.sort(), ['id', 'name', 'role'].sort());

    // Strict absence of private fields
    assert.strictEqual(profile.email, undefined);
    assert.strictEqual(profile.points, undefined);
    assert.strictEqual(profile.joined_at, undefined);
    assert.strictEqual(profile.password, undefined);
    assert.strictEqual(profile.google_id, undefined);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('8. getPublicUserProfile translates HTTP 404 into ApiError', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => ({
    ok: false,
    status: 404,
    json: async () => ({ detail: 'User not found.' }),
  });

  try {
    await getPublicUserProfile(999);
    assert.fail('Expected 404 ApiError');
  } catch (err) {
    assert.ok(err instanceof ApiError);
    assert.strictEqual(err.status, 404);
    assert.strictEqual(err.message, 'User not found.');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('9. getPublicUserProfile translates HTTP 503 into ApiError without exposing database internals', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => ({
    ok: false,
    status: 503,
    json: async () => ({ detail: 'Database service is currently unavailable.' }),
  });

  try {
    await getPublicUserProfile(123);
    assert.fail('Expected 503 ApiError');
  } catch (err) {
    assert.ok(err instanceof ApiError);
    assert.strictEqual(err.status, 503);
    assert.strictEqual(err.message, 'Database service is currently unavailable.');
    assert.ok(!err.message.includes('postgres'), 'Must not expose raw DB internals');
    assert.ok(!err.message.includes('supabase.co'), 'Must not expose Supabase internals');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('10. getPublicUserProfile propagates network/connection failures', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => {
    throw new TypeError('Failed to fetch');
  };

  try {
    await getPublicUserProfile(123);
    assert.fail('Expected network error');
  } catch (err) {
    assert.ok(err instanceof TypeError);
    assert.strictEqual(err.message, 'Failed to fetch');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('11. Security Invariants: No localStorage / sessionStorage token storage', () => {
  assert.strictEqual(typeof globalThis.localStorage, 'undefined', 'localStorage must not be defined or used');
  assert.strictEqual(typeof globalThis.sessionStorage, 'undefined', 'sessionStorage must not be defined or used');
});
