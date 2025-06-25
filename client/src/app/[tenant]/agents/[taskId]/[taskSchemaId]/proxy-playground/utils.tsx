import { GeneralizedTaskInput, TaskSchemaResponseWithSchema } from '@/types';
import { JsonSchema } from '@/types/json_schema';
import { CacheUsage, ProxyMessage, TaskGroupProperties_Input, ToolKind, VersionV1 } from '@/types/workflowAI';
import { allTools } from '../playground/components/Toolbox/utils';
import { AdvancedSettings } from './hooks/useProxyPlaygroundSearchParams';

export type ProxyPlaygroundModels = {
  model1: string | undefined;
  model2: string | undefined;
  model3: string | undefined;
  modelReasoning1: string | undefined;
  modelReasoning2: string | undefined;
  modelReasoning3: string | undefined;
};

export function getModelAndReasoning(
  index: number,
  models: ProxyPlaygroundModels | undefined
): {
  model: string | undefined;
  reasoning: string | undefined;
} {
  if (!models) {
    return { model: undefined, reasoning: undefined };
  }

  switch (index) {
    case 0:
      return { model: models.model1, reasoning: models.modelReasoning1 };
    case 1:
      return { model: models.model2, reasoning: models.modelReasoning2 };
    case 2:
      return { model: models.model3, reasoning: models.modelReasoning3 };
    default:
      return { model: undefined, reasoning: undefined };
  }
}

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

export function removeInputEntriesNotMatchingSchema(
  input: Record<string, unknown>,
  schema: JsonSchema | undefined
): Record<string, unknown> | unknown[] {
  if (!schema) {
    return input;
  }

  // Handle array type
  if (schema.type === 'array' && Array.isArray(input)) {
    if (!schema.items) {
      return [];
    }

    // Handle tuple validation (items is an array of schemas)
    if (Array.isArray(schema.items)) {
      const itemsArray = schema.items as JsonSchema[];
      return input.map((item, index) => {
        const itemSchema = index < itemsArray.length ? itemsArray[index] : undefined;
        if (typeof item === 'object' && item !== null && itemSchema) {
          return removeInputEntriesNotMatchingSchema(item as Record<string, unknown>, itemSchema);
        }
        return item;
      });
    }

    // Handle single schema for all items
    return input.map((item) => {
      if (typeof item === 'object' && item !== null) {
        return removeInputEntriesNotMatchingSchema(item as Record<string, unknown>, schema.items as JsonSchema);
      }
      return item;
    });
  }

  // Handle object type
  if (schema.type === 'object' && typeof input === 'object' && input !== null && !Array.isArray(input)) {
    if (!('properties' in schema) || !schema.properties) {
      return input;
    }

    const schemaProperties = Object.keys(schema.properties);
    const filteredInput: Record<string, unknown> = {};

    for (const key of Object.keys(input)) {
      if (schemaProperties.includes(key)) {
        const propertySchema = schema.properties[key] as JsonSchema;
        const value = input[key];

        if (propertySchema.type === 'array' && Array.isArray(value)) {
          if (propertySchema.items && Array.isArray(propertySchema.items)) {
            // Handle tuple validation
            const itemsArray = propertySchema.items as JsonSchema[];
            filteredInput[key] = value.map((item, index) => {
              const itemSchema = index < itemsArray.length ? itemsArray[index] : undefined;
              if (typeof item === 'object' && item !== null && itemSchema) {
                return removeInputEntriesNotMatchingSchema(item as Record<string, unknown>, itemSchema);
              }
              return item;
            });
          } else if (propertySchema.items) {
            // Handle single schema for all items
            filteredInput[key] = value.map((item) => {
              if (typeof item === 'object' && item !== null) {
                return removeInputEntriesNotMatchingSchema(
                  item as Record<string, unknown>,
                  propertySchema.items as JsonSchema
                );
              }
              return item;
            });
          } else {
            filteredInput[key] = value;
          }
        } else if (propertySchema.type === 'object' && typeof value === 'object' && value !== null) {
          filteredInput[key] = removeInputEntriesNotMatchingSchema(value as Record<string, unknown>, propertySchema);
        } else {
          filteredInput[key] = value;
        }
      }
    }

    return filteredInput;
  }

  return input;
}

export function removeInputEntriesNotMatchingSchemaAndKeepMessages(
  input: Record<string, unknown> | undefined,
  schema: JsonSchema | undefined
): Record<string, unknown> | undefined {
  if (!input) {
    return undefined;
  }

  if (!schema) {
    return input;
  }

  const inputMessages = (input['workflowai.messages'] as ProxyMessage[] | undefined) ?? [];
  const cleanedInput = removeInputEntriesNotMatchingSchema(input, schema);

  if (Array.isArray(cleanedInput)) {
    return input;
  }

  return { ...cleanedInput, 'workflowai.messages': inputMessages };
}

export function addAdvencedSettingsToProperties(
  properties: TaskGroupProperties_Input,
  advancedSettings: AdvancedSettings | undefined
): TaskGroupProperties_Input {
  if (!advancedSettings) {
    return properties;
  }

  const {
    temperature,
    cache,
    top_p: topP,
    max_tokens: maxTokens,
    stream,
    stream_options_include_usage,
    stop,
    presence_penalty,
    frequency_penalty,
    tool_choice,
  } = advancedSettings;

  const result = { ...properties };

  if (temperature !== undefined) {
    result.temperature = Number(temperature);
  }

  if (cache !== undefined) {
    result.use_cache = cache;
  }

  if (topP !== undefined) {
    result.top_p = Number(topP);
  }

  if (maxTokens !== undefined) {
    result.max_tokens = Number(maxTokens);
  }

  if (stream !== undefined) {
    result.stream = stream === 'true';
  }

  if (stream_options_include_usage !== undefined) {
    result.stream_options_include_usage = stream_options_include_usage === 'true';
  }

  if (stop !== undefined) {
    result.stop = stop;
  }

  if (presence_penalty !== undefined) {
    result.presence_penalty = Number(presence_penalty);
  }

  if (frequency_penalty !== undefined) {
    result.frequency_penalty = Number(frequency_penalty);
  }

  if (tool_choice !== undefined) {
    result.tool_choice = tool_choice;
  }

  return result;
}

export function getUseCache(cache: string | undefined): CacheUsage {
  if (cache === undefined) {
    return 'auto' as CacheUsage;
  }

  switch (cache) {
    case 'auto':
      return 'auto' as CacheUsage;
    case 'always':
      return 'always' as CacheUsage;
    case 'never':
      return 'never' as CacheUsage;
    case 'when_available':
      return 'when_available' as CacheUsage;
    case 'only':
      return 'only' as CacheUsage;
    default:
      return 'auto' as CacheUsage;
  }
}

export function defaultValueForAdvencedSetting(name: string): string | undefined {
  switch (name) {
    case 'cache':
      return 'auto';
    case 'temperature':
      return '1';
    case 'top_p':
      return '1.0';
    case 'max_tokens':
      return undefined;
    case 'stream':
      return 'false';
    case 'stream_options_include_usage':
      return 'false';
    case 'stop':
      return undefined;
    case 'presence_penalty':
      return '0';
    case 'frequency_penalty':
      return '0';
    case 'tool_choice':
      return undefined;
    default:
      return undefined;
  }
}

export function advencedSettingNameFromKey(key: string): string {
  switch (key) {
    case 'cache':
      return 'Use cache';
    case 'temperature':
      return 'Temperature';
    case 'top_p':
      return 'Top P';
    case 'max_tokens':
      return 'Max tokens';
    case 'stream':
      return 'Stream';
    case 'stream_options_include_usage':
      return 'Stream Options';
    case 'stop':
      return 'Stop';
    case 'presence_penalty':
      return 'Presence Penalty';
    case 'frequency_penalty':
      return 'Frequency Penalty';
    case 'tool_choice':
      return 'Tool Choice';
    default:
      return key;
  }
}

export const advencedSettingsVersionPropertiesKeys = [
  'cache',
  'top_p',
  'max_tokens',
  'stream',
  'stream_options_include_usage',
  'stop',
  'presence_penalty',
  'frequency_penalty',
  'tool_choice',
];

export function getToolsFromMessages(messages: ProxyMessage[] | undefined): ToolKind[] | undefined {
  if (!messages) return undefined;
  const result = allTools.filter((tool) =>
    messages.some((message) =>
      message.content.some((content) => content.text?.toLowerCase().includes(tool.toLowerCase()))
    )
  );
  return result.length > 0 ? result : undefined;
}

export function generatePromptForToolsUpdate(oldTools: ToolKind[], newTools: ToolKind[]): string | undefined {
  const toolsRemoved = oldTools.filter((tool) => !newTools.includes(tool));
  const toolsAdded = newTools.filter((tool) => !oldTools.includes(tool));
  const toolsNotChanged = oldTools.filter((tool) => newTools.includes(tool));

  const promptParts: string[] = [];

  if (toolsRemoved.length > 0) {
    promptParts.push(`Remove the tools from the messages: ${toolsRemoved.join(', ')}`);
  }

  if (toolsAdded.length > 0) {
    promptParts.push(`Add the tools to the messages: ${toolsAdded.join(', ')}`);
  }

  if (promptParts.length === 0) {
    return undefined;
  }

  if (toolsNotChanged.length > 0) {
    promptParts.push(
      `Keep the tools in the messages (make sure you are not removing them by accident): ${toolsNotChanged.join(', ')}`
    );
  }

  promptParts.push(
    'DO NOT use markdown formatting (**, *, #, etc.), unless markdown is already present in the massages'
  );

  return `${promptParts.join('. ')}.`;
}

export function cleanChunkOutput(output: Record<string, unknown>) {
  const keys = Object.keys(output);
  if (keys.length === 1 && keys[0] === 'content' && typeof output.content === 'string') {
    return output.content;
  }
  return output;
}
