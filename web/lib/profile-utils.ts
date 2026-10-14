/**
 * Profile utilities for formatting and client-side validation.
 * Conforms strictly to the backend validation contracts.
 */

export function validateProfileName(name: string): string | null {
  const trimmed = name.trim();
  if (trimmed.length === 0) {
    return 'Name cannot be empty or whitespace only.';
  }
  if (trimmed.length < 2) {
    return 'Name must be at least 2 characters long.';
  }
  if (trimmed.length > 150) {
    return 'Name must not exceed 150 characters.';
  }
  return null;
}

export function formatRoleName(role: string | null | undefined): string {
  if (!role) return 'Learner';
  const r = role.toLowerCase().trim();
  if (r === 'learner') return 'Learner';
  if (r === 'creator') return 'Creator';
  if (r === 'admin') return 'Admin';
  return r.charAt(0).toUpperCase() + r.slice(1);
}

export function formatJoinedDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Not available';
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

/**
 * Generates deterministic 1-2 letter initials from a display name.
 * e.g. "Mohammed Ibrahim" -> "MI", "Alex" -> "AL", "" -> "U"
 */
export function getInitials(name: string | null | undefined): string {
  if (!name || !name.trim()) return 'U';
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/**
 * Validates whether a raw string/param is a positive integer user ID.
 * Returns the parsed positive integer or null if invalid.
 */
export function parseUserId(rawId: string | number | undefined | null): number | null {
  if (rawId === undefined || rawId === null) return null;
  const str = String(rawId).trim();
  if (!/^\d+$/.test(str)) return null;
  const num = parseInt(str, 10);
  if (num <= 0 || !Number.isSafeInteger(num)) return null;
  return num;
}
