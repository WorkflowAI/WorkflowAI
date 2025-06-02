import { ProxyMessage } from '@/types/workflowAI';

export function changeTextToHTML(text: string) {
  // First escape any existing HTML/XML tags
  const escapedText = text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
  // Then convert newlines to <br> tags
  return escapedText.replace(/\n/g, '<br>').trim();
}

export function changeHTMLToText(html: string) {
  return html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n')
    .replace(/<p>/gi, '')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .trim();
}

function textInProxyMessages(messages: ProxyMessage[] | undefined): string | undefined {
  if (!messages) return undefined;
  let text = '';
  for (const message of messages) {
    message.content.forEach((content) => {
      if (!!content.text) {
        text += content.text;
      }
    });
  }
  return text;
}

export function extractInputKeysFromMessages(messages: ProxyMessage[] | undefined): string[] | undefined {
  if (!messages) return undefined;

  const text = textInProxyMessages(messages);
  if (!text) return undefined;

  const regex = /\{\{([a-zA-Z0-9_]+)\}\}/g;
  const matches = text.match(regex);

  if (!matches) return undefined;
  const cleanedMatches = matches.map((match) => match.replace('{{', '').replace('}}', '').trim().toLowerCase());
  return cleanedMatches.filter((key, index, self) => self.indexOf(key) === index);
}
