import { elementIdForMessage } from './elementIdForMessage';

describe('elementIdForMessage', () => {
  const userMsg = (overrides = {}) => ({ role: 'user' as const, content: [], ...overrides });
  const assistantMsg = (overrides = {}) => ({ role: 'assistant' as const, content: [], ...overrides });

  it('returns "last-user-message" for penultimate user message followed by assistant', () => {
    const messages = [userMsg(), assistantMsg()];
    expect(elementIdForMessage(messages, 0)).toBe('last-user-message');
  });

  it('returns "first-message" for the first message', () => {
    const messages = [userMsg(), assistantMsg()];
    expect(elementIdForMessage(messages, 0)).toBe('last-user-message'); // special case
    expect(elementIdForMessage([userMsg(), userMsg()], 0)).toBe('first-message');
  });

  it('returns "last-message" for the last message', () => {
    const messages = [userMsg(), assistantMsg()];
    expect(elementIdForMessage(messages, 1)).toBe('last-message');
  });

  it('returns undefined for a middle message', () => {
    const messages = [userMsg(), assistantMsg(), userMsg(), assistantMsg()];
    expect(elementIdForMessage(messages, 1)).toBe(undefined);
  });
});
