import { GeneralizedTaskInput, TaskSchemaResponseWithSchema } from '@/types';
import { JsonSchema } from '@/types/json_schema';
import { ProxyMessage, VersionV1 } from '@/types/workflowAI';

export function checkInputSchemaForInputVaribles(inputSchema: JsonSchema | undefined) {
  if (!inputSchema) {
    return false;
  }
  return 'properties' in inputSchema && inputSchema.properties;
}

export function checkInputSchemaForProxy(inputSchema: JsonSchema) {
  return inputSchema.format === 'messages';
}

export function checkSchemaForProxy(schema: TaskSchemaResponseWithSchema) {
  const inputSchema = schema.input_schema.json_schema;
  return checkInputSchemaForProxy(inputSchema);
}

export function checkVersionForProxy(version: VersionV1 | undefined) {
  if (!version) {
    return false;
  }

  if (version.input_schema) {
    return checkInputSchemaForProxy(version.input_schema as JsonSchema);
  }

  return false;
}

export function findMessagesInVersion(version: VersionV1 | undefined) {
  if (!version) {
    return undefined;
  }
  return version.properties.messages as ProxyMessage[];
}

export function numberOfInputVariblesInInputSchema(inputSchema: JsonSchema | undefined): number {
  if (!!inputSchema && 'properties' in inputSchema && inputSchema.properties) {
    return Object.keys(inputSchema.properties).length;
  }
  return 0;
}

export function repairMessageKeyInInput(input: GeneralizedTaskInput | undefined) {
  if (!input) {
    return undefined;
  }

  const keys = Object.keys(input);
  if (keys.length === 1 && keys[0] === 'messages') {
    // change the key from 'messages' to 'workflowai.messages'
    const newInput = { 'workflowai.messages': (input as Record<string, unknown>)['messages'] };
    delete (newInput as Record<string, unknown>)['messages'];
    return newInput as GeneralizedTaskInput;
  }

  if (keys.includes('workflowai.replies')) {
    // change the key from 'workflowai.replies' to 'workflowai.messages'
    const newInput = { 'workflowai.messages': (input as Record<string, unknown>)['workflowai.replies'] };
    delete (newInput as Record<string, unknown>)['workflowai.replies'];
    return newInput as GeneralizedTaskInput;
  }

  return input;
}

export function moveInputMessagesToVersionIfRequired(
  input: GeneralizedTaskInput | undefined,
  messages: ProxyMessage[] | undefined
) {
  if (!input) {
    return { input, messages };
  }

  if (!!messages && messages.length > 0) {
    return { input, messages };
  }

  // There are no messages in the version, so we need to move some of the messages from the input to the version

  const inputMessages = (input as Record<string, unknown>)['workflowai.messages'] as ProxyMessage[];
  if (!inputMessages || inputMessages.length === 0) {
    return { input, messages };
  }

  // There are messages in the input, so we need to move some of them to the version

  const lastSystemMessageIndex = inputMessages.findLastIndex((message) => message.role === 'system');
  const lastIndexOfMessagesToMove = lastSystemMessageIndex === -1 ? 0 : lastSystemMessageIndex;

  const messagesToMove = inputMessages.slice(0, lastIndexOfMessagesToMove + 1);
  const messagesToKeep = inputMessages.slice(lastIndexOfMessagesToMove + 1);

  const newInput = { ...input, 'workflowai.messages': messagesToKeep };

  return { input: newInput, messages: messagesToMove };
}
