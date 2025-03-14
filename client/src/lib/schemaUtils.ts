/* eslint-disable max-lines */
import { captureException } from '@sentry/nextjs';
import dayjs from 'dayjs';
import { AUDIO_REF_NAME, IMAGE_REF_NAME, PDF_REF_NAME } from '@/lib/constants';
import {
  JsonArraySchema,
  JsonObjectSchema,
  JsonSchemaDefinitions,
  JsonValueSchema,
  sanitizeRef,
} from '@/types';
import { extractFileFieldType } from './schemaEditorUtils';
import { isFileSchema } from './schemaFileUtils';

export type FieldType =
  | 'string'
  | 'integer'
  | 'number'
  | 'boolean'
  | 'array'
  | 'object'
  | 'date'
  | 'date-time'
  | 'timezone'
  | 'time'
  | 'html'
  | 'image'
  | 'undefined'
  | 'null'
  | 'unknown'
  | 'audio'
  | 'document';

export function viewerType(
  schema: JsonValueSchema | undefined,
  defs: JsonSchemaDefinitions | undefined,
  value?: unknown
): FieldType {
  if (schema?.type === 'string' && schema.format === 'date-time') {
    return 'date-time';
  }
  if (
    value instanceof Date ||
    (schema?.type === 'string' && schema.format === 'date')
  ) {
    return 'date';
  }
  if (schema?.type === 'string' && schema.format === 'timezone') {
    return 'timezone';
  }
  if (schema?.type === 'string' && schema.format === 'time') {
    return 'time';
  }
  if (schema?.type === 'string' && schema.format === 'html') {
    return 'html';
  }
  if (!!schema && isFileSchema(schema)) {
    return extractFileFieldType(schema, value) as FieldType;
  }

  if (!!schema && '$ref' in schema) {
    const refName = sanitizeRef(schema.$ref);
    switch (refName) {
      case IMAGE_REF_NAME:
        return 'image';
      case AUDIO_REF_NAME:
        return 'audio';
      case PDF_REF_NAME:
        return 'document';
    }
    if (!!defs) {
      const refSchema = defs[refName];
      if (!refSchema) {
        captureException(`Definition ${refName} not found`);
        return 'string';
      }
      return viewerType(refSchema, defs, value);
    }
  }
  const fieldType = schema?.type ?? typeof value;
  if (fieldType === 'string') {
    return 'string';
  }
  if (fieldType === 'integer') {
    return 'integer';
  }
  if (fieldType === 'number') {
    return 'number';
  }
  if (fieldType === 'boolean') {
    return 'boolean';
  }
  if (fieldType === 'array') {
    return 'array';
  }
  if (fieldType === 'object') {
    return 'object';
  }
  if (value === undefined) {
    return 'undefined';
  }
  if (value === null) {
    return 'null';
  }
  return 'unknown';
}

export type SchemaNodeType =
  | Record<string, unknown>
  | unknown[]
  | string
  | number
  | boolean
  | null
  | Date;

export enum InitInputFromSchemaMode {
  NOTHING = 'nothing',
  VOID = 'void',
  TYPE = 'type',
  EXAMPLE = 'example',
}

export function parseSchemaNode(
  valueSchema: JsonValueSchema,
  defs: JsonSchemaDefinitions | undefined,
  mode: InitInputFromSchemaMode = InitInputFromSchemaMode.TYPE
): SchemaNodeType {
  if ('$ref' in valueSchema) {
    if (!defs) {
      throw new Error('Schema defs not found');
    }
    const ref = valueSchema.$ref;
    // ref has the following format: #/$defs/CalendarEvent
    const parsedRef = ref.split('/').pop();
    if (!parsedRef) {
      throw new Error(`Invalid ref ${ref} for defs ${defs}`);
    }
    const refSchema = defs[parsedRef];
    if (!refSchema) {
      throw new Error(`Schema reference ${ref} not found for defs ${defs}`);
    }
    return parseSchemaNode(refSchema, defs, mode);
  }
  if ('anyOf' in valueSchema) {
    return parseSchemaNode(valueSchema.anyOf[0], defs, mode);
  }
  if ('oneOf' in valueSchema) {
    return parseSchemaNode(valueSchema.oneOf[0], defs, mode);
  }
  if ('allOf' in valueSchema) {
    return parseSchemaNode(valueSchema.allOf[0], defs, mode);
  }
  if ('items' in valueSchema) {
    if (!valueSchema.items) {
      return mode === InitInputFromSchemaMode.TYPE ? 'array' : [];
    }
    const item = Array.isArray(valueSchema.items)
      ? valueSchema.items[0]
      : valueSchema.items;
    return [parseSchemaNode(item, defs, mode)];
  }
  if ('properties' in valueSchema) {
    return Object.entries(valueSchema?.properties || {}).reduce(
      (acc, [key, value]) => {
        acc[key] = parseSchemaNode(value, defs, mode);
        return acc;
      },
      {} as Record<string, unknown>
    );
  }
  if (mode === InitInputFromSchemaMode.TYPE && 'enum' in valueSchema) {
    return valueSchema.enum?.join('|') || 'string';
  }
  const type = viewerType(valueSchema, defs);

  switch (mode) {
    case InitInputFromSchemaMode.NOTHING:
      return null;
    case InitInputFromSchemaMode.TYPE:
      return type;
    case InitInputFromSchemaMode.VOID:
      switch (type) {
        case 'string':
        case 'timezone':
        case 'time':
        case 'html':
          return '';
        case 'integer':
        case 'number':
          return 0;
        case 'boolean':
          return false;
        case 'date':
          return dayjs().format('YYYY-MM-DD');
        default:
          return null;
      }
    case InitInputFromSchemaMode.EXAMPLE:
      switch (type) {
        case 'string':
          return 'this is a string';
        case 'timezone':
          return 'Europe/London';
        case 'time':
          return '12:00:00';
        case 'html':
          return '<p>this is a html</p>';
        case 'integer':
          return 123;
        case 'number':
          return 123.456;
        case 'boolean':
          return true;
        case 'date':
          return dayjs('2024-01-01').format('YYYY-MM-DD');
        case 'date-time':
          return dayjs('2024-01-01T12:00:00Z').format('YYYY-MM-DDTHH:mm:ssZ');
        default:
          return null;
      }
  }
}

export function initInputFromSchema(
  schema: JsonObjectSchema | JsonArraySchema | undefined,
  defs: JsonSchemaDefinitions | undefined,
  mode: InitInputFromSchemaMode = InitInputFromSchemaMode.TYPE
): Record<string, unknown> | SchemaNodeType[] | undefined {
  if (!schema) {
    return undefined;
  }
  if ('properties' in schema) {
    return Object.entries(schema?.properties || {}).reduce(
      (acc, [key, value]) => {
        acc[key] = parseSchemaNode(value, defs, mode);
        return acc;
      },
      {} as Record<string, unknown>
    );
  }
  if ('items' in schema) {
    if (!schema.items) {
      return [];
    }
    const item = Array.isArray(schema.items) ? schema.items[0] : schema.items;
    const parsed = parseSchemaNode(item, defs, mode);
    return [parsed];
  }
  return undefined;
}

export function resetTaskOutput(
  taskOutput: Record<string, unknown> | undefined
): Record<string, unknown> | undefined {
  if (!taskOutput) {
    return undefined;
  }
  const result: Record<string, unknown> = {};
  Object.keys(taskOutput).forEach((key) => {
    switch (typeof taskOutput[key]) {
      case 'string':
        result[key] = '';
        break;
      case 'number':
        result[key] = 0;
        break;
      case 'boolean':
        result[key] = false;
        break;
      case 'object':
        const value = taskOutput[key];
        if (value instanceof Date) {
          result[key] = null;
          break;
        }
        result[key] = Array.isArray(taskOutput[key])
          ? []
          : resetTaskOutput(taskOutput[key] as Record<string, unknown>);
        break;
      default:
        result[key] = taskOutput[key];
    }
  });
  return result;
}

export enum FieldEvaluationOptions {
  FLEXIBLE_ORDERING = 'Flexible Ordering',
  STRICT_ORDERING = 'Strict Ordering',
  STRICTLY_EQUAL = 'Strictly Equal',
  SOFT_EQUAL = 'Soft Equal',
  SEMANTICALLY_EQUAL = 'Semantically Equal',
  IGNORE = 'Ignore',
}

export type ObjectKeyType = {
  path: string;
  type: FieldType;
  value: FieldEvaluationOptions;
};

/* eslint-disable no-use-before-define */

export function mergeRequiredFields(
  oldSchema: JsonValueSchema,
  newSchema: JsonValueSchema
): string[] | undefined {
  const oldRequired = ('required' in oldSchema && oldSchema.required) || [];
  const newRequired = ('required' in newSchema && newSchema.required) || [];

  const uniqueRequiredFields = new Set([...oldRequired, ...newRequired]);

  const mergedRequired = Array.from(uniqueRequiredFields);
  return mergedRequired.length > 0 ? mergedRequired : undefined;
}

export function mergeDefs(
  oldSchema: JsonValueSchema,
  newSchema: JsonValueSchema
): JsonSchemaDefinitions | undefined {
  const oldDefs = ('$defs' in oldSchema && oldSchema.$defs) || {};
  const newDefs = ('$defs' in newSchema && newSchema.$defs) || {};

  const mergedDefs = {
    ...oldDefs,
    ...newDefs,
  };

  return Object.keys(mergedDefs).length > 0 ? mergedDefs : undefined;
}

export function mergeItems(
  oldSchema: JsonValueSchema,
  newSchema: JsonValueSchema
): JsonValueSchema | JsonValueSchema[] | undefined {
  if (
    !('items' in oldSchema) ||
    !('items' in newSchema) ||
    !oldSchema.items ||
    !newSchema.items
  ) {
    if ('items' in newSchema && newSchema.items) {
      return newSchema.items;
    }
    if ('items' in oldSchema && oldSchema.items) {
      return oldSchema.items;
    }
    return undefined;
  }

  if (Array.isArray(oldSchema.items) && Array.isArray(newSchema.items)) {
    return newSchema.items.map((item, index) =>
      index < (oldSchema.items as JsonValueSchema[]).length
        ? mergeSchemas((oldSchema.items as JsonValueSchema[])[index], item) ??
          item
        : item
    );
  }

  if (!Array.isArray(oldSchema.items) && !Array.isArray(newSchema.items)) {
    return mergeSchemas(oldSchema.items, newSchema.items) ?? newSchema.items;
  }

  return newSchema.items;
}

export function mergeProperties(
  oldSchema: JsonValueSchema,
  newSchema: JsonValueSchema
): { [key: string]: JsonValueSchema } | undefined {
  if (
    !('properties' in oldSchema) ||
    !('properties' in newSchema) ||
    !oldSchema.properties ||
    !newSchema.properties
  ) {
    if ('properties' in newSchema && newSchema.properties) {
      return newSchema.properties;
    }
    if ('properties' in oldSchema && oldSchema.properties) {
      return oldSchema.properties;
    }
    return undefined;
  }

  const mergedProperties = { ...oldSchema.properties };

  Object.entries(newSchema.properties).forEach(([key, newValue]) => {
    const oldValue = oldSchema.properties?.[key];
    const mergedValue = oldValue ? mergeSchemas(oldValue, newValue) : newValue;

    if (!!mergedValue) {
      mergedProperties[key] = mergedValue;
    }
  });

  return mergedProperties;
}

export function mergeSchemas(
  oldSchema: JsonValueSchema | null | undefined,
  newSchema: JsonValueSchema | null | undefined
): JsonValueSchema | null | undefined {
  if (!newSchema) {
    return oldSchema;
  }

  if (!oldSchema) {
    return newSchema;
  }

  const type = newSchema.type || oldSchema.type;

  const result = {
    ...oldSchema,
    ...newSchema,
    type,
  } as JsonValueSchema;

  const mergedProps = {
    $defs: mergeDefs(oldSchema, newSchema),
    properties: mergeProperties(oldSchema, newSchema),
    items: mergeItems(oldSchema, newSchema),
    required: mergeRequiredFields(oldSchema, newSchema),
  };

  // Only add properties that are defined
  Object.entries(mergedProps).forEach(([key, value]) => {
    if (value !== undefined) {
      (result as Record<string, unknown>)[key] = value;
    }
  });

  return result;
}

/* eslint-enable no-use-before-define */
