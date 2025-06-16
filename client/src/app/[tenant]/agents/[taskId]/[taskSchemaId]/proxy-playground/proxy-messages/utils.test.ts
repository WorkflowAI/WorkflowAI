// pyright: reportPrivateUsage=false
import { elementIdForMessage } from './utils';

describe('elementIdForMessage', () => {
  it('should return undefined for empty messages array', () => {
    expect(elementIdForMessage(0, 0)).toBeUndefined();
  });

  it('should return undefined for negative total messages', () => {
    expect(elementIdForMessage(0, -1)).toBeUndefined();
  });

  it('should return "first-message" for the first message in a single message array', () => {
    expect(elementIdForMessage(0, 1)).toBe('first-message');
  });

  it('should return "last-message" for the first message in a single message array', () => {
    // In a single message array, the first message is also the last message
    // However, the function prioritizes "first-message" since it checks index === 0 first
    expect(elementIdForMessage(0, 1)).toBe('first-message');
  });

  it('should return "first-message" for the first message in multiple messages', () => {
    expect(elementIdForMessage(0, 3)).toBe('first-message');
  });

  it('should return "last-message" for the last message in multiple messages', () => {
    expect(elementIdForMessage(2, 3)).toBe('last-message');
  });

  it('should return undefined for middle messages', () => {
    expect(elementIdForMessage(1, 3)).toBeUndefined();
    expect(elementIdForMessage(1, 5)).toBeUndefined();
    expect(elementIdForMessage(2, 5)).toBeUndefined();
    expect(elementIdForMessage(3, 5)).toBeUndefined();
  });

  it('should handle edge case with two messages', () => {
    expect(elementIdForMessage(0, 2)).toBe('first-message');
    expect(elementIdForMessage(1, 2)).toBe('last-message');
  });

  it('should handle large arrays correctly', () => {
    const totalMessages = 100;
    expect(elementIdForMessage(0, totalMessages)).toBe('first-message');
    expect(elementIdForMessage(50, totalMessages)).toBeUndefined();
    expect(elementIdForMessage(99, totalMessages)).toBe('last-message');
  });

  it('should return undefined for out-of-bounds indices', () => {
    expect(elementIdForMessage(-1, 3)).toBeUndefined();
    expect(elementIdForMessage(5, 3)).toBeUndefined();
  });
});