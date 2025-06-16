import { DeviceEq16Regular, Document16Regular, FluentIcon, Image16Regular } from '@fluentui/react-icons';
import { nanoid } from 'nanoid';
import {
  ProxyMessage,
  ProxyMessageContent,
  ProxyMessageWithID,
  RunV1,
  ToolCallRequestWithID,
  ToolCallResult,
} from '@/types/workflowAI';

export type MessageType = 'user' | 'system' | 'assistant';
export type ExtendedMessageType = MessageType | 'toolCallResult' | 'toolCallRequest';
export type ContentType = 'text' | 'document' | 'image' | 'audio' | 'toolCallResult' | 'toolCallRequest';

export const allExtendedMessageTypes: ExtendedMessageType[] = [
  'user',
  'system',
  'assistant',
  'toolCallResult',
  'toolCallRequest',
];

export function getAvaibleMessageTypes(source: 'input' | 'version'): ExtendedMessageType[] {
  switch (source) {
    case 'input':
      return ['user', 'assistant', 'toolCallResult'];
    case 'version':
      return ['system', 'user'];
  }
}

export function getExtendedMessageType(type: MessageType, content?: ProxyMessageContent[]): ExtendedMessageType {
  if (type === 'system') {
    return 'system';
  }

  if (!content || content.length === 0) {
    return type;
  }

  if (type === 'user' && content.some((entry) => !!entry.tool_call_result)) {
    return 'toolCallResult';
  }

  if (type === 'assistant' && content.some((entry) => !!entry.tool_call_request)) {
    return 'toolCallRequest';
  }

  return type;
}

export function getMessageType(type: ExtendedMessageType): MessageType {
  switch (type) {
    case 'user':
      return 'user';
    case 'system':
      return 'system';
    case 'assistant':
      return 'assistant';
    case 'toolCallResult':
      return 'user';
    case 'toolCallRequest':
      return 'assistant';
  }
}

export function getContentTypes(type: ExtendedMessageType): ContentType[] {
  switch (type) {
    case 'user':
      return ['text', 'document', 'image', 'audio'];
    case 'assistant':
      return ['text', 'document', 'image', 'audio'];
    case 'toolCallResult':
      return ['toolCallResult'];
    case 'toolCallRequest':
      return ['text', 'document', 'image', 'audio', 'toolCallRequest'];
    case 'system':
      return ['text'];
  }
}

export function requiredContentTypeForType(type: ExtendedMessageType): ContentType | undefined {
  switch (type) {
    case 'toolCallResult':
      return 'toolCallResult';
    case 'toolCallRequest':
      return 'toolCallRequest';
    default:
      return undefined;
  }
}

export function getContentTypeForContent(content: ProxyMessageContent | undefined): ContentType | undefined {
  if (!content) {
    return undefined;
  }

  if ('text' in content && content.text) {
    return 'text';
  }

  if ('tool_call_request' in content && content.tool_call_request) {
    return 'toolCallRequest';
  }

  if ('tool_call_result' in content && content.tool_call_result) {
    return 'toolCallResult';
  }

  if ('file' in content && content.file?.content_type?.startsWith('image/')) {
    return 'image';
  }

  if ('file' in content && content.file?.content_type?.startsWith('audio/')) {
    return 'audio';
  }

  if ('file' in content && content.file) {
    return 'document';
  }

  return undefined;
}

export function getContentTypesToShowToUser(type: ExtendedMessageType): ContentType[] {
  switch (type) {
    case 'user':
      return ['document', 'image', 'audio'];
    case 'assistant':
      return ['document', 'image', 'audio'];
    case 'toolCallResult':
      return [];
    case 'toolCallRequest':
      return ['document', 'image', 'audio'];
    case 'system':
      return [];
  }
}

export function getTextAndIconFotContentType(type: ContentType): { text: string; icon: FluentIcon } | undefined {
  switch (type) {
    case 'image':
      return { text: 'Upload Image', icon: Image16Regular };
    case 'audio':
      return { text: 'Upload Audio', icon: DeviceEq16Regular };
    case 'document':
      return { text: 'Upload File', icon: Document16Regular };
    default:
      return undefined;
  }
}

export function getTitleForType(type: ExtendedMessageType) {
  switch (type) {
    case 'user':
      return 'User Message';
    case 'system':
      return 'System Message';
    case 'assistant':
      return 'Assistant Message';
    case 'toolCallResult':
      return 'Tool Call Result';
    case 'toolCallRequest':
      return 'Tool Call Request';
  }
}

export function isProxyMessageContentEmpty(content: ProxyMessageContent): boolean {
  if (!!content.file?.data || !!content.file?.url) {
    return false;
  }

  if (!!content.tool_call_request?.id && !!content.tool_call_request?.tool_input_dict) {
    return false;
  }

  if (!!content.tool_call_result?.id && !!content.tool_call_result?.result) {
    return false;
  }

  if (!!content.text && content.text.trim() !== '' && content.text.length > 0) {
    return false;
  }

  return true;
}

export function createEmptyMessageContent(type?: ContentType, previouseMessage?: ProxyMessage): ProxyMessageContent {
  if (!type) {
    return {
      text: undefined,
      file: undefined,
      tool_call_request: undefined,
      tool_call_result: undefined,
    };
  }

  switch (type) {
    case 'text':
      return { text: '', file: undefined, tool_call_request: undefined, tool_call_result: undefined };
    case 'document':
      return {
        text: undefined,
        file: {
          content_type: 'application/pdf',
        },
        tool_call_request: undefined,
        tool_call_result: undefined,
      };
    case 'image':
      return {
        text: undefined,
        file: {
          content_type: 'image/jpeg',
        },
        tool_call_request: undefined,
        tool_call_result: undefined,
      };
    case 'audio':
      return {
        text: undefined,
        file: {
          content_type: 'audio/mpeg',
        },
        tool_call_request: undefined,
        tool_call_result: undefined,
      };
    case 'toolCallResult':
      const request = previouseMessage?.content.find((content) => !!content.tool_call_request);

      const id = request?.tool_call_request?.id ?? nanoid(10);
      const toolName = request?.tool_call_request?.tool_name ?? '';
      const toolInputDict = request?.tool_call_request?.tool_input_dict ?? {};

      return {
        text: undefined,
        file: undefined,
        tool_call_result: {
          id: id,
          result: 'Result of the tool call',
          tool_name: toolName,
          tool_input_dict: toolInputDict,
        } as ToolCallResult,
      };
    case 'toolCallRequest':
      const result = previouseMessage?.content.find((content) => !!content.tool_call_result);

      const toolCallRequestId = result?.tool_call_result?.id ?? nanoid(10);
      const toolCallRequestToolName = result?.tool_call_result?.tool_name ?? '';
      const toolCallRequestToolInputDict = result?.tool_call_result?.tool_input_dict ?? {
        parameter: 'value',
      };

      return {
        text: undefined,
        file: undefined,
        tool_call_request: {
          tool_input_dict: toolCallRequestToolInputDict,
          tool_name: toolCallRequestToolName,
          id: toolCallRequestId,
        } as ToolCallRequestWithID,
      };
  }
}

export function createEmptyMessage(role: ExtendedMessageType, previouseMessage?: ProxyMessage): ProxyMessage {
  return {
    role: getMessageType(role),
    content: [createEmptyMessageContent(undefined, previouseMessage)],
  };
}

export function formatResponseToText(response: unknown) {
  if (!response) return undefined;

  const text = typeof response === 'string' ? response : JSON.stringify(response);

  try {
    const json = JSON.parse(text);
    return JSON.stringify(json, null, 2);
  } catch {
    return text;
  }
}

export function formatTextToResponse(text: string | undefined): unknown {
  if (!text) return undefined;

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function mergeTextContentInRow(content: ProxyMessageContent[]): ProxyMessageContent[] {
  if (content.length <= 1) {
    return content;
  }

  const result: ProxyMessageContent[] = [];
  let currentTextContent: ProxyMessageContent | null = null;

  for (const item of content) {
    if (item.text !== undefined) {
      if (currentTextContent === null) {
        currentTextContent = { ...item };
      } else {
        const currentText = currentTextContent.text || '';
        const newText = item.text || '';
        currentTextContent.text = currentText + '\n' + newText;
      }
    } else {
      if (currentTextContent !== null) {
        result.push(currentTextContent);
        currentTextContent = null;
      }
      result.push(item);
    }
  }

  if (currentTextContent !== null) {
    result.push(currentTextContent);
  }

  return result;
}

export function cleanMessageContent(content: ProxyMessageContent[]): ProxyMessageContent[] {
  const filteredContent = content.filter((entry) => {
    if (entry.text?.trim() === '') {
      return false;
    }

    return (
      entry.file !== undefined ||
      entry.text !== undefined ||
      entry.tool_call_request !== undefined ||
      entry.tool_call_result !== undefined
    );
  });

  const mergedContent = mergeTextContentInRow(filteredContent);

  if (mergedContent.length === 0) {
    return [createEmptyMessageContent('text')];
  }

  const lastContent = mergedContent[mergedContent.length - 1];
  const contentType = getContentTypeForContent(lastContent);

  if (
    contentType !== 'text' &&
    contentType !== 'toolCallResult' &&
    contentType !== 'toolCallRequest' &&
    contentType !== undefined
  ) {
    return [...mergedContent, createEmptyMessageContent('text')];
  }

  return mergedContent;
}

export function cleanMessagesAndAddIDs(messages: ProxyMessage[] | undefined): ProxyMessageWithID[] | undefined {
  if (!messages || messages.length === 0) {
    return undefined;
  }

  const cleanedMessages = messages.map((message) => {
    const id: string = 'internal_id' in message && !!message.internal_id ? (message.internal_id as string) : nanoid();
    return {
      ...message,
      content: cleanMessageContent(message.content),
      internal_id: id,
    };
  });

  return cleanedMessages;
}

export function removeIdsFromMessages(messages: ProxyMessageWithID[]): ProxyMessage[] {
  return messages.map((message) => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { internal_id, ...rest } = message;
    return rest;
  });
}

export function createAssistantMessageFromRun(run: RunV1): ProxyMessage {
  const toolCallRequests = run.tool_call_requests ?? [];

  const content: ProxyMessageContent[] = [];

  toolCallRequests.forEach((toolCallRequest) => {
    content.push({
      tool_call_request: {
        tool_name: toolCallRequest.name,
        tool_input_dict: toolCallRequest.input,
        id: toolCallRequest.id,
      },
    });
  });

  const assistantText = JSON.stringify(run.task_output);

  return {
    role: 'assistant',
    run_id: run.id,
    content: [...content, { text: assistantText }],
  };
}

/**
 * Generates element ID for a message based on its position in the message list
 * @param index - The index of the message in the messages array
 * @param totalMessages - The total number of messages
 * @returns The element ID string or undefined for middle messages
 */
export function elementIdForMessage(index: number, totalMessages: number): string | undefined {
  if (totalMessages <= 0) {
    return undefined;
  }
  
  if (index === 0) {
    return 'first-message';
  }
  
  if (index === totalMessages - 1) {
    return 'last-message';
  }
  
  return undefined;
}
