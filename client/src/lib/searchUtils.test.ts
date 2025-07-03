import { flexibleStringMatch, normalizeSearchString } from './searchUtils';

describe('searchUtils', () => {
  describe('flexibleStringMatch', () => {
    it('matches strings with different separators', () => {
      expect(flexibleStringMatch('o3 mini', 'o3-mini')).toBe(true);
      expect(flexibleStringMatch('gpt 4o', 'gpt-4o')).toBe(true);
      expect(flexibleStringMatch('claude_3_5', 'claude-3.5')).toBe(true);
    });

    it('matches partial strings', () => {
      expect(flexibleStringMatch('mini', 'o3-mini-latest')).toBe(true);
      expect(flexibleStringMatch('gpt', 'gpt-4o-latest')).toBe(true);
    });

    it('returns false for non-matching strings', () => {
      expect(flexibleStringMatch('o3 mini', 'gpt-4o')).toBe(false);
      expect(flexibleStringMatch('claude', 'gemini')).toBe(false);
    });
  });
});
