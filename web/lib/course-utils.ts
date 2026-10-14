/**
 * Course utilities for formatting, category/level color schemes, and client validation.
 * Conforms strictly to the backend validation contracts.
 */

/**
 * Validates whether a raw string/param is a positive integer course ID.
 * Returns the parsed positive integer or null if invalid.
 */
export function parseCourseId(rawId: string | number | undefined | null): number | null {
  if (rawId === undefined || rawId === null) return null;
  const str = String(rawId).trim();
  if (!/^\d+$/.test(str)) return null;
  const num = parseInt(str, 10);
  if (num <= 0 || !Number.isSafeInteger(num)) return null;
  return num;
}

/**
 * Format course monetary price.
 */
export function formatCoursePrice(price: number | undefined | null): string {
  if (price === undefined || price === null || price <= 0) {
    return 'Free';
  }
  return `$${price}`;
}

/**
 * Format course points price.
 */
export function formatPointsPrice(points: number | undefined | null): string {
  if (points === undefined || points === null || points <= 0) {
    return '0 pts';
  }
  return `${points.toLocaleString()} pts`;
}

/**
 * Level badge color theme (symmetric and distinct).
 */
export function getLevelBadgeStyle(level: string | undefined | null): {
  bg: string;
  text: string;
  border: string;
} {
  const normalized = (level || 'Beginner').toLowerCase().trim();
  switch (normalized) {
    case 'beginner':
      return {
        bg: 'bg-emerald-50 dark:bg-emerald-950/40',
        text: 'text-emerald-700 dark:text-emerald-300',
        border: 'border-emerald-200 dark:border-emerald-800/60',
      };
    case 'intermediate':
      return {
        bg: 'bg-amber-50 dark:bg-amber-950/40',
        text: 'text-amber-700 dark:text-amber-300',
        border: 'border-amber-200 dark:border-amber-800/60',
      };
    case 'advanced':
      return {
        bg: 'bg-purple-50 dark:bg-purple-950/40',
        text: 'text-purple-700 dark:text-purple-300',
        border: 'border-purple-200 dark:border-purple-800/60',
      };
    default:
      return {
        bg: 'bg-zinc-50 dark:bg-zinc-800/40',
        text: 'text-zinc-700 dark:text-zinc-300',
        border: 'border-zinc-200 dark:border-zinc-700',
      };
  }
}
