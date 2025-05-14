/* eslint-disable max-lines */
import { captureException } from '@sentry/nextjs';
import { cloneDeep, isEqual } from 'lodash';
import { viewerType } from '@/lib/schemaUtils';
import {
  BaseSchema,
  JsonRefSchema,
  JsonSchema,
  JsonSchemaDefinitions,
  JsonSchemaNumberExtraFields,
  JsonSchemaStringExtraFields,
  JsonValueSchema,
  sanitizeRef,
} from '@/types';
import { AUDIO_REF_NAME, FILE_REF_NAMES, IMAGE_REF_NAME } from './constants';

export const IMAGE_REF: JsonRefSchema = {
  $ref: '#/$defs/Image',
};

export const FILE_REF: JsonRefSchema = {
  $ref: '#/$defs/File',
};

export type SelectableFieldType =
  | 'string'
  | 'boolean'
  | 'number'
  | 'integer'
  | 'date'
  | 'date-time'
  | 'time'
  | 'timezone'
  | 'html'
  | 'array'
  | 'object'
  | 'enum'
  | 'image'
  | 'audio'
  | 'document';

const FILE_SELECTABLE_FIELD_TYPES: SelectableFieldType[] = ['image', 'audio', 'document'];

function fieldFromValue(value: unknown): SelectableFieldType | undefined {
  if (!value || typeof value !== 'object' || !('content_type' in value) || typeof value.content_type !== 'string') {
    return undefined;
  }
  const contentType = value.content_type;
  if (contentType.startsWith('image/')) {
    return 'image';
  }
  if (contentType.startsWith('audio/')) {
    return 'audio';
  }
  if (contentType.startsWith('application/pdf')) {
    return 'document';
  }
  return undefined;
}

export function extractFileFieldType(schema: JsonValueSchema, value?: unknown): SelectableFieldType {
  const field = fieldFromValue(value);
  if (field) {
    return field;
  }
  switch (schema.format) {
    case 'image':
      return 'image';
    case 'audio':
      return 'audio';
    case 'document':
    case 'pdf':
    case 'text':
      return 'document';
    default:
      return 'document';
  }
}

function extractFormatFromFieldType(type: SelectableFieldType | undefined): string | undefined {
  switch (type) {
    case 'image':
      return 'image';
    case 'audio':
      return 'audio';
    case 'document':
      return 'document';
    default:
      return undefined;
  }
}

function fieldTypeToSelectableFieldType(
  schema: JsonValueSchema,
  definitions: JsonSchemaDefinitions | undefined
): SelectableFieldType {
  if ('properties' in schema) {
    return 'object';
  }

  if ('enum' in schema) {
    return 'enum';
  }

  if ('$ref' in schema) {
    const refName = sanitizeRef(schema.$ref);

    if (IMAGE_REF_NAME === refName) {
      return 'image';
    }

    if (FILE_REF_NAMES.includes(refName)) {
      return extractFileFieldType(schema);
    }

    if (!!definitions) {
      const refSchema = definitions[refName];
      if (!refSchema) {
        captureException(`Definition ${refName} not found`);
        return 'string';
      }
      return fieldTypeToSelectableFieldType(refSchema, definitions);
    }

    return 'string';
  }
  const type = viewerType(schema, definitions);
  switch (type) {
    case 'undefined':
    case 'null':
    case 'unknown':
      return 'string';
    default:
      return type;
  }
}

export function extractStringFormats(type: SelectableFieldType): string | undefined {
  switch (type) {
    case 'date':
      return 'date';
    case 'date-time':
      return 'date-time';
    case 'time':
      return 'time';
    case 'timezone':
      return 'timezone';
    case 'html':
      return 'html';
    default:
      return undefined;
  }
}

type BaseSchemaFieldsWithoutType = Omit<BaseSchema, 'type'>;

type SchemaEditorSplattedCommonFields = JsonSchemaNumberExtraFields &
  JsonSchemaStringExtraFields &
  BaseSchemaFieldsWithoutType;

export type SchemaEditorField = SchemaEditorSplattedCommonFields & {
  keyName: string;
  type: SelectableFieldType;
  arrayType?: SelectableFieldType;
  fields?: SchemaEditorField[];
};

function extractBaseFields(data: JsonValueSchema | SchemaEditorField): BaseSchemaFieldsWithoutType {
  const result: BaseSchemaFieldsWithoutType = {};
  if (data.title) {
    result.title = data.title;
  }
  if (data.description) {
    result.description = data.description;
  }
  if (data.examples) {
    result.examples = data.examples;
  }
  if (data.default !== undefined) {
    result.default = data.default;
  }
  return result;
}

function extractNumberFields(data: JsonValueSchema | SchemaEditorField): JsonSchemaNumberExtraFields {
  const result: JsonSchemaNumberExtraFields = {};
  if ('minimum' in data) {
    result.minimum = data.minimum;
  }
  if ('maximum' in data) {
    result.maximum = data.maximum;
  }
  return result;
}

function extractStringFields(data: JsonValueSchema | SchemaEditorField): JsonSchemaStringExtraFields {
  const result: JsonSchemaStringExtraFields = {};
  if ('pattern' in data) {
    result.pattern = data.pattern;
  }
  if ('enum' in data) {
    result.enum = data.enum;
  }
  return result;
}

export function fromSchemaToSplattedEditorFields(
  schema: JsonValueSchema | undefined,
  keyName: string = '',
  definitions?: JsonSchemaDefinitions | undefined
): SchemaEditorField | undefined {
  if (!schema) {
    return undefined;
  }
  let result: SchemaEditorField | undefined;
  if ('properties' in schema && schema.properties) {
    result = {
      keyName,
      type: 'object',
      fields: Object.entries(schema.properties)
        .map(([key, value]) => fromSchemaToSplattedEditorFields(value, key, definitions))
        .filter((x) => x !== undefined) as SchemaEditorField[],
    };
  } else if (schema.type === 'array' && !!schema.items) {
    const items = Array.isArray(schema.items) ? schema.items[0] : schema.items;
    const arrayType = fieldTypeToSelectableFieldType(items, definitions);
    const field = fromSchemaToSplattedEditorFields(items, keyName, definitions);
    let fields: SchemaEditorField[] | undefined;
    if (field?.type === 'object') {
      fields = field.fields;
    } else if (!!field && field?.type !== 'image') {
      fields = [field];
    }
    result = {
      keyName,
      type: 'array',
      arrayType,
      fields,
    };
  } else if ('$ref' in schema) {
    const refName = sanitizeRef(schema.$ref);

    if (IMAGE_REF_NAME === refName) {
      return {
        keyName,
        type: 'image',
      };
    }

    if (AUDIO_REF_NAME === refName) {
      return {
        keyName,
        type: 'audio',
      };
    }

    if (FILE_REF_NAMES.includes(refName)) {
      return {
        keyName,
        type: extractFileFieldType(schema),
      };
    }

    if (!!definitions) {
      const refSchema = definitions[refName];
      if (!refSchema) {
        captureException(`Definition ${refName} not found`);
        return undefined;
      }
      return fromSchemaToSplattedEditorFields(refSchema, keyName, definitions);
    }
    return undefined;
  } else if ('anyOf' in schema && schema.anyOf) {
    const firstNonNull = schema.anyOf.find((x) => x.type !== 'null');
    if (firstNonNull) {
      return fromSchemaToSplattedEditorFields(firstNonNull, keyName, definitions);
    }
    return undefined;
  } else if ('oneOf' in schema && schema.oneOf) {
    const firstNonNull = schema.oneOf.find((x) => x.type !== 'null');
    if (firstNonNull) {
      return fromSchemaToSplattedEditorFields(firstNonNull, keyName, definitions);
    }
    return undefined;
  } else if ('allOf' in schema && schema.allOf) {
    const firstNonNull = schema.allOf.find((x) => x.type !== 'null');
    if (firstNonNull) {
      return fromSchemaToSplattedEditorFields(firstNonNull, keyName, definitions);
    }
    return undefined;
  } else if (schema.type === 'string') {
    result = {
      ...extractStringFields(schema),
      keyName,
      type: !!schema.enum ? 'enum' : fieldTypeToSelectableFieldType(schema, definitions),
    };
  } else if (schema.type === 'number') {
    result = {
      ...extractNumberFields(schema),
      keyName,
      type: fieldTypeToSelectableFieldType(schema, definitions),
    };
  } else {
    result = {
      keyName,
      type: fieldTypeToSelectableFieldType(schema, definitions),
    };
  }
  return !!result
    ? {
        ...extractBaseFields(schema),
        ...result,
      }
    : undefined;
}

export function fromSplattedEditorFieldsToSchema(
  splattedEditorFields: SchemaEditorField,
  definitions?: JsonSchemaDefinitions | undefined
): { schema: JsonValueSchema; definitions: JsonSchemaDefinitions } {
  let result: JsonValueSchema | undefined;
  let definitionsCopy = definitions ? cloneDeep(definitions) : {};

  if (splattedEditorFields.type === 'object') {
    // We are now supporting empty objects
    if (!splattedEditorFields.fields) {
      result = {
        type: 'object',
        properties: {},
      };
    } else {
      const properties = splattedEditorFields.fields.reduce((acc, field) => {
        const { schema: fieldSchema, definitions } = fromSplattedEditorFieldsToSchema(field, definitionsCopy);
        definitionsCopy = definitions;
        return {
          ...acc,
          [field.keyName]: fieldSchema,
        };
      }, {});

      result = {
        type: 'object',
        properties,
      };
    }
  } else if (splattedEditorFields.type === 'array') {
    if (splattedEditorFields.arrayType === 'image') {
      result = {
        type: 'array',
        items: IMAGE_REF,
      };
    } else if (
      !!splattedEditorFields.arrayType &&
      FILE_SELECTABLE_FIELD_TYPES.includes(splattedEditorFields.arrayType)
    ) {
      result = {
        type: 'array',
        items: {
          ...FILE_REF,
          format: extractFormatFromFieldType(splattedEditorFields.arrayType),
        },
      };
    } else if (!splattedEditorFields.fields) {
      // This can happen if the underlying object schema has no properties but only additionalProperties
      // See refObject test case to reproduce
      console.warn('Array type has no fields');
      result = {
        type: 'array',
        items: {},
      };
    } else if (splattedEditorFields.arrayType === 'object') {
      result = {
        type: 'array',
        items: {
          type: 'object',
          properties: splattedEditorFields.fields.reduce((acc, field) => {
            const { schema: fieldSchema, definitions } = fromSplattedEditorFieldsToSchema(field, definitionsCopy);
            definitionsCopy = definitions;
            return {
              ...acc,
              [field.keyName]: fieldSchema,
            };
          }, {}),
        },
      };
    } else {
      const { schema: items, definitions } = fromSplattedEditorFieldsToSchema(
        splattedEditorFields.fields[0],
        definitionsCopy
      );
      definitionsCopy = definitions;
      result = {
        type: 'array',
        items,
      };
    }
  } else if (['string', 'html', 'date', 'date-time', 'timezone', 'time', 'enum'].includes(splattedEditorFields.type)) {
    result = {
      ...extractStringFields(splattedEditorFields),
      type: 'string',
    };
    const format = extractStringFormats(splattedEditorFields.type);
    if (!!format) {
      result.format = format;
    }
    if (splattedEditorFields.type === 'enum') {
      result.enum = splattedEditorFields.enum;
    }
  } else if (splattedEditorFields.type === 'number' || splattedEditorFields.type === 'integer') {
    result = {
      ...extractNumberFields(splattedEditorFields),
      type: splattedEditorFields.type,
    };
  } else if (splattedEditorFields.type === 'image') {
    result = IMAGE_REF;
  } else if (!!splattedEditorFields.type && FILE_SELECTABLE_FIELD_TYPES.includes(splattedEditorFields.type)) {
    result = {
      ...FILE_REF,
      format: extractFormatFromFieldType(splattedEditorFields.type),
    };
  } else if (splattedEditorFields.type === 'boolean') {
    result = {
      type: splattedEditorFields.type,
    };
  } else {
    // This should never happen
    captureException(`Unknown type ${splattedEditorFields.type}`);
    result = {
      type: 'string',
      description: 'A simple dictionary field',
    };
  }
  return {
    schema: {
      ...extractBaseFields(splattedEditorFields),
      ...result,
    },
    definitions: definitionsCopy,
  };
}

export function shouldDisableRemove(schema: SchemaEditorField | undefined): boolean {
  if (!schema) {
    return true;
  }
  return (schema.type === 'object' || schema.arrayType === 'object') && !!schema.fields && schema.fields?.length < 2;
}

const IGNORED_DEFS_FOR_COMPARISON = ['Image', 'File', 'Audio', 'DatetimeLocal'];

function sanitizeDefsForComparison(schema: JsonSchema) {
  if (!schema.$defs) {
    // Making sure we have an empty dict
    return {
      ...schema,
      $defs: {},
    };
  }
  const sanitizedDefs = Object.entries(schema.$defs).reduce((acc, [key, value]) => {
    if (IGNORED_DEFS_FOR_COMPARISON.includes(key)) {
      return acc;
    }
    return {
      ...acc,
      [key]: value,
    };
  }, {});
  return {
    ...schema,
    $defs: sanitizedDefs,
  };
}

/**
 * Compares objects for structural equality, maintaining order only for property objects
 * under a 'properties' key.
 */
function orderSensitiveCompare(obj1: unknown, obj2: unknown, parentKey?: string): boolean {
  // If primitives or different types, use direct comparison
  if (obj1 === obj2) return true;
  if (typeof obj1 !== typeof obj2) return false;
  if (obj1 === null || obj2 === null) return obj1 === obj2;

  // Handle arrays (order always matters)
  if (Array.isArray(obj1) && Array.isArray(obj2)) {
    if (obj1.length !== obj2.length) return false;
    return obj1.every((val, idx) => orderSensitiveCompare(val, obj2[idx]));
  }

  // Handle objects
  if (typeof obj1 === 'object' && typeof obj2 === 'object' && obj1 !== null && obj2 !== null) {
    const keys1 = Object.keys(obj1 as Record<string, unknown>);
    const keys2 = Object.keys(obj2 as Record<string, unknown>);

    if (keys1.length !== keys2.length) return false;

    // Order matters specifically for objects under 'properties' key
    const isPropertiesObject = parentKey === 'properties';

    if (isPropertiesObject) {
      // Check if keys are in the same order for property objects
      if (!keys1.every((key, idx) => key === keys2[idx])) return false;

      // Check all values, passing the key name for context
      return keys1.every((key) =>
        orderSensitiveCompare((obj1 as Record<string, unknown>)[key], (obj2 as Record<string, unknown>)[key], key)
      );
    } else {
      // For all other objects, order doesn't matter, so we use a different approach
      // Sort keys to normalize the order for comparison
      const sortedKeys1 = [...keys1].sort();
      const sortedKeys2 = [...keys2].sort();

      // Check if the same keys exist
      if (!sortedKeys1.every((key, idx) => key === sortedKeys2[idx])) return false;

      // Check all values using sorted keys
      return sortedKeys1.every((key) =>
        orderSensitiveCompare((obj1 as Record<string, unknown>)[key], (obj2 as Record<string, unknown>)[key], key)
      );
    }
  }

  return false;
}

export function areSchemasEquivalent(
  schema1: JsonSchema | undefined,
  schema2: JsonSchema | undefined,
  isOrderImportant: boolean = false
) {
  if (!schema1 || !schema2) {
    return false;
  }

  const sanitizedSchema1 = sanitizeDefsForComparison(schema1);
  const sanitizedSchema2 = sanitizeDefsForComparison(schema2);

  // eslint-disable-next-line no-console
  console.log('sanitizedSchema1', JSON.stringify(sanitizedSchema1));
  // eslint-disable-next-line no-console
  console.log('sanitizedSchema2', JSON.stringify(sanitizedSchema2));

  // For order-insensitive comparison (original behavior)
  if (!isOrderImportant) {
    return isEqual(sanitizedSchema1, sanitizedSchema2);
  }

  // For order-sensitive comparison
  return orderSensitiveCompare(sanitizedSchema1, sanitizedSchema2);
}
