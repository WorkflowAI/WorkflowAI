/**
 * Normalizes a string for flexible search by removing/replacing common separators
 * and converting to lowercase for case-insensitive matching
 */
export function normalizeSearchString(str: string): string {
  return str
    .toLowerCase()
    .replace(/[\s\-_\.]/g, '') // Remove spaces, hyphens, underscores, and dots
    .trim();
}

/**
 * Performs a flexible search that matches strings even when they use different
 * separators (spaces vs hyphens vs underscores)
 */
export function flexibleStringMatch(searchQuery: string, targetString: string): boolean {
  const normalizedQuery = normalizeSearchString(searchQuery);
  const normalizedTarget = normalizeSearchString(targetString);

  return normalizedTarget.includes(normalizedQuery);
}
