/**
 * Phase 4, Stage 7E - Profile Navigation & Frontend Integration Test Suite
 * Validates profile navigation targets, public profile links, ID validation,
 * accessibility semantics, security invariants, and compatibility with Stage 7C/7D.
 */

import test from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  parseUserId,
} from './lib/profile-utils.ts';

import {
  getAuthenticatedProfile,
  getPublicUserProfile,
} from './lib/api.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Helper to inspect component source code for static verification
function readComponentFile(relativePath) {
  return fs.readFileSync(path.join(__dirname, relativePath), 'utf8');
}

test('1. Profile navigation in Navbar points directly to /profile', () => {
  const navbarSource = readComponentFile('components/navigation/Navbar.tsx');
  
  // Must contain Next.js Link pointing to /profile
  assert.match(navbarSource, /href=["']\/profile["']/);
  // Must have accessible label
  assert.match(navbarSource, /aria-label=["'][^"']*profile[^"']*["']/i);
  // Must also contain Home link pointing to /
  assert.match(navbarSource, /href=["']\/["']/);
});

test('2. Public profile link helper/component constructs valid /users/{userId} routes', () => {
  const linkSource = readComponentFile('components/profile/UserProfileLink.tsx');
  
  // Must use Next.js Link
  assert.match(linkSource, /import Link from ["']next\/link["']/);
  // Must construct path /users/${validId}
  assert.match(linkSource, /\/users\/\$\{validId\}/);
  // Must use parseUserId validation
  assert.match(linkSource, /parseUserId\(userId\)/);
});

test('3. Invalid user IDs are rejected and prevent navigation', () => {
  const invalidCases = ['abc', '0', '-5', '1.5', '', '  ', null, undefined, '123/edit', '../admin', '1; DROP'];
  
  for (const invalid of invalidCases) {
    const parsed = parseUserId(invalid);
    assert.strictEqual(parsed, null, `Invalid user ID "${invalid}" must be rejected by parseUserId`);
  }
});

test('4. Valid user IDs are parsed correctly for public profile navigation', () => {
  assert.strictEqual(parseUserId(1), 1);
  assert.strictEqual(parseUserId('42'), 42);
  assert.strictEqual(parseUserId('999999'), 999999);
  assert.strictEqual(parseUserId('  100  '), 100);
});

test('5. Navigation and link components do not contain private user fields or email', () => {
  const navbarSource = readComponentFile('components/navigation/Navbar.tsx');
  const linkSource = readComponentFile('components/profile/UserProfileLink.tsx');
  
  // Navbar should not reference email, password, or tokens
  assert.doesNotMatch(navbarSource, /email/i);
  assert.doesNotMatch(navbarSource, /token/i);
  assert.doesNotMatch(navbarSource, /jwt/i);
  
  // UserProfileLink should not reference private fields
  assert.doesNotMatch(linkSource, /email/i);
  assert.doesNotMatch(linkSource, /password/i);
  assert.doesNotMatch(linkSource, /token/i);
});

test('6. Profile page (/profile) provides clear return navigation to Home', () => {
  const profilePageSource = readComponentFile('app/profile/page.tsx');
  
  // Must contain Back to Home link
  assert.match(profilePageSource, /href=["']\/["']/);
  assert.match(profilePageSource, /Back to Home/i);
});

test('7. Public profile page (/users/[userId]) provides clear navigation actions', () => {
  const publicProfilePageSource = readComponentFile('app/users/[userId]/page.tsx');
  
  // Must contain Home navigation link
  assert.match(publicProfilePageSource, /href=["']\/["']/);
  assert.match(publicProfilePageSource, />\s*Home\s*<\/Link>/);
  // Must contain Go Back button
  assert.match(publicProfilePageSource, /Go Back/i);
});

test('8. Security Invariants: No localStorage, sessionStorage, or document.cookie', () => {
  const navbarSource = readComponentFile('components/navigation/Navbar.tsx');
  const linkSource = readComponentFile('components/profile/UserProfileLink.tsx');
  const layoutSource = readComponentFile('app/layout.tsx');
  const homeSource = readComponentFile('app/page.tsx');
  
  const sources = [navbarSource, linkSource, layoutSource, homeSource];
  
  for (const src of sources) {
    assert.doesNotMatch(src, /localStorage/);
    assert.doesNotMatch(src, /sessionStorage/);
    assert.doesNotMatch(src, /document\.cookie/);
    assert.doesNotMatch(src, /dangerouslySetInnerHTML/);
    assert.doesNotMatch(src, /\beval\b/);
  }
});

test('9. Security Invariants: No Bearer tokens in API requests', async () => {
  let interceptedHeaders = null;
  const originalFetch = globalThis.fetch;
  
  try {
    globalThis.fetch = async (url, options) => {
      interceptedHeaders = options?.headers;
      return {
        ok: true,
        status: 200,
        json: async () => ({ id: 42, name: 'Alice Walker', role: 'creator' }),
      };
    };

    const profile = await getPublicUserProfile(42);
    assert.strictEqual(profile.id, 42);
    
    // Check headers
    if (interceptedHeaders) {
      const authHeader = interceptedHeaders.Authorization || interceptedHeaders.authorization;
      assert.strictEqual(authHeader, undefined, 'Must NEVER send Authorization Bearer header');
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('10. Compatibility with Stage 7C profile retrieval', async () => {
  let capturedOptions = null;
  const originalFetch = globalThis.fetch;
  
  try {
    globalThis.fetch = async (url, options) => {
      capturedOptions = options;
      return {
        ok: true,
        status: 200,
        json: async () => ({
          id: 1,
          email: 'user@nexora.app',
          name: 'Stage 7C User',
          role: 'learner',
          created_at: '2026-01-01T00:00:00Z',
        }),
      };
    };

    const user = await getAuthenticatedProfile();
    assert.strictEqual(user.id, 1);
    assert.strictEqual(user.name, 'Stage 7C User');
    assert.strictEqual(capturedOptions.credentials, 'include', 'Stage 7C credentials must be include');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('11. Compatibility with Stage 7D public profile retrieval', async () => {
  let capturedUrl = null;
  const originalFetch = globalThis.fetch;
  
  try {
    globalThis.fetch = async (url) => {
      capturedUrl = url.toString();
      return {
        ok: true,
        status: 200,
        json: async () => ({
          id: 99,
          name: 'Stage 7D Public User',
          role: 'admin',
        }),
      };
    };

    const publicProfile = await getPublicUserProfile(99);
    assert.strictEqual(publicProfile.id, 99);
    assert.strictEqual(publicProfile.role, 'admin');
    assert.match(capturedUrl, /\/api\/v1\/users\/99$/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
