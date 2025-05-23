import { useMemo } from 'react';
import { TaskSchemaResponseWithSchema } from '@/types';
import { JsonSchema } from '@/types/json_schema';
import { ProxyMessage, VersionV1 } from '@/types/workflowAI';

export function checkInputSchemaForInputVaribles(inputSchema: JsonSchema) {
  return inputSchema.format === 'messages' && 'properties' in inputSchema;
}

function checkInputSchemaForProxy(inputSchema: JsonSchema) {
  return inputSchema.format === 'messages';
}

function checkSchemaForProxy(schema: TaskSchemaResponseWithSchema) {
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

function findMessagesInVersion(version: VersionV1 | undefined) {
  if (!version) {
    return undefined;
  }
  return version.properties.messages as ProxyMessage[];
}

export function useIsProxy(schema: TaskSchemaResponseWithSchema, version: VersionV1 | undefined) {
  const isProxy: boolean = useMemo(() => {
    return checkSchemaForProxy(schema);
  }, [schema]);

  const hasInputVariables = useMemo(() => {
    return checkInputSchemaForInputVaribles(schema.input_schema.json_schema);
  }, [schema]);

  const messages = useMemo(() => {
    return findMessagesInVersion(version);
  }, [version]);

  return { isProxy, hasInputVariables, messages };
}
