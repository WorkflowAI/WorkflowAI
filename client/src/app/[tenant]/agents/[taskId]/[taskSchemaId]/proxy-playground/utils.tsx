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
  input: Record<string, unknown>,
  schema: JsonSchema | undefined
): Record<string, unknown> {
  if (!schema) {
    return input;
  }

  const inputMessages = input['workflowai.messages'] as ProxyMessage[] | undefined;
  const cleanedInput = removeInputEntriesNotMatchingSchema(input, schema);

  if (Array.isArray(cleanedInput)) {
    return input;
  }

  if (!!inputMessages) {
    return { ...cleanedInput, 'workflowai.messages': inputMessages };
  }

  return cleanedInput;
}
