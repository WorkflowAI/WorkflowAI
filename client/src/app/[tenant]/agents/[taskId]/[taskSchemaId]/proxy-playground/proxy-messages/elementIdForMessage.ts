import { ProxyMessage } from '@/types/workflowAI';

export function elementIdForMessage(messages: ProxyMessage[], index: number) {
  if (
    index === messages.length - 2 &&
    messages.length - 2 >= 0 &&
    messages[messages.length - 2].role === 'user' &&
    messages[messages.length - 1].role === 'assistant'
  ) {
    return 'last-user-message';
  }

  if (index === 0) {
    return 'first-message';
  }

  if (index === messages.length - 1) {
    return 'last-message';
  }

  return undefined;
}
