export type MessagePreparedForDisplay = {
  title: string;
  text: string;
  orginalText: string;
};

export function extractTextFromContent(content: unknown) {
  let text: string;
  let orginalText: string;

  if (typeof content === 'string') {
    text = content;
    orginalText = text;
  } else if (content && typeof content === 'object') {
    text = JSON.stringify(
      content,
      (_, value) => {
        if (typeof value === 'string' && value.startsWith('data:')) {
          const idx = value.indexOf(',');
          if (idx > 0) {
            return value.substring(0, idx) + ',...truncated';
          }
        }
        return value;
      },
      2
    );
    text = '```json' + text + '```';
    orginalText = JSON.stringify(content, null, 2);
  } else {
    text = String(content);
    orginalText = text;
  }

  return { text, orginalText };
}

export function prepareMessageForDisplay(message: Record<string, unknown>): MessagePreparedForDisplay {
  let title: string;
  let text: string = '';
  let orginalText: string = '';

  const role = message['role'] as string | undefined;

  switch (role) {
    case 'user':
      title = 'User';
      break;
    case 'system':
      title = 'System';
      break;
    case 'assistant':
      title = 'Assistant';
      break;
    default:
      title = 'Message';
  }

  const content = message['content'] ?? message['text'];

  if (content) {
    const { text: extractedText, orginalText: extractedOriginalText } = extractTextFromContent(content);
    text = extractedText;
    orginalText = extractedOriginalText;
  } else {
    const parts = message['parts'] as Record<string, unknown>[];
    if (parts !== undefined) {
      parts.forEach((part: Record<string, unknown>) => {
        const content = part['text'] as string;
        if (content) {
          const { text: extractedText, orginalText: extractedOriginalText } = extractTextFromContent(content);
          text += extractedText;
          orginalText += extractedOriginalText;
        }
      });
    }
  }

  return {
    title: title,
    text: text,
    orginalText: orginalText,
  };
}

export function processResponse(response: string | undefined | null) {
  if (!response) {
    return undefined;
  }

  const trimmedResponse = response.trim();
  if (trimmedResponse.startsWith('{') && trimmedResponse.endsWith('}')) {
    try {
      const parsedJson = JSON.parse(trimmedResponse);
      const formattedJson = JSON.stringify(parsedJson, null, 2);
      return '```json\n' + formattedJson + '\n```';
    } catch {
      return response;
    }
  }
  return response;
}
