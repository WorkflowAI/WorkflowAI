/**
 * Calculates the difference between two texts by finding where the new text
 * overlaps with the old text. This is useful for handling streaming responses
 * where new chunks of text need to be merged with existing text.
 *
 * The algorithm:
 * 1. Handles empty string cases first
 * 2. For each position in the new text, takes the remaining substring
 * 3. Looks for that substring in the old text
 * 4. When found, combines:
 *    - the complete new text
 *    - any remaining text from the old string after the overlap
 * 5. If no overlap is found, simply concatenates the strings
 *
 * @param oldText - The existing text
 * @param newText - The new text to merge
 * @returns The merged text preserving as much of both strings as possible
 */
export function calculateTextDiff(oldText: string | undefined, newText: string | undefined): string {
  if (!newText?.length) {
    return oldText ?? '';
  }

  if (!oldText?.length) {
    return newText ?? '';
  }

  for (let i = 0; i < newText.length; i++) {
    const endPart = newText.slice(i);
    const index = oldText.indexOf(endPart);
    if (index !== -1) {
      return newText + oldText.slice(index + endPart.length);
    }
  }

  return newText + oldText.slice(newText.length);
}
