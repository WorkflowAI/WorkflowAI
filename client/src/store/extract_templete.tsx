import { enableMapSet, produce } from 'immer';
import { debounce, unset } from 'lodash';
import { useCallback, useMemo, useState } from 'react';
import { useEffect } from 'react';
import { useRef } from 'react';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { RequestError } from '@/lib/api/client';
import { areSchemasEquivalent } from '@/lib/schemaEditorUtils';
import { mergeSchemaTypesAndDefs } from '@/lib/schemaUtils';
import { TaskID, TenantID } from '@/types/aliases';
import { JsonSchema } from '@/types/json_schema';
import { ProxyMessage } from '@/types/workflowAI';
import { taskSubPath } from './utils';

enableMapSet();

export type ExtractTempleteError = {
  code: string;
  message: string;
  status_code: number;
};

interface ExtractTempleteState {
  schemaById: Map<string, JsonSchema>;
  isLoadingById: Map<string, boolean>;
  errorById: Map<string, ExtractTempleteError>;

  extract: (
    id: string,
    tenant: TenantID | undefined,
    taskId: TaskID,
    messages: ProxyMessage[],
    inputSchema: JsonSchema | undefined,
    signal?: AbortSignal
  ) => Promise<void>;
}

export const useExtractTemplete = create<ExtractTempleteState>((set, get) => ({
  schemaById: new Map(),
  isLoadingById: new Map(),
  errorById: new Map(),

  extract: async (id, tenant, taskId, messages, inputSchema, signal) => {
    if (get().isLoadingById.get(id)) return;
    set(
      produce((state) => {
        state.isLoadingById.set(id, true);
      })
    );

    const path = taskSubPath(tenant, taskId, '/templates/extract', true);

    try {
      const { json_schema } = await client.post<
        { messages: ProxyMessage[]; base_schema?: JsonSchema },
        { json_schema: JsonSchema }
      >(
        path,
        {
          messages,
          base_schema: inputSchema,
        },
        signal
      );

      set(
        produce((state) => {
          state.schemaById.set(id, json_schema ?? { type: 'object', properties: {} });
          state.isLoadingById.set(id, false);
          state.errorById.set(id, undefined);
        })
      );
    } catch (error) {
      if (signal?.aborted) {
        set(
          produce((state) => {
            state.isLoadingById.set(id, false);
          })
        );
        return;
      }

      if (error instanceof RequestError) {
        try {
          const errorResponse = JSON.parse(error.rawResponse).error as ExtractTempleteError;
          set(
            produce((state) => {
              state.isLoadingById.set(id, false);
              state.errorById.set(id, errorResponse);
            })
          );
        } catch (e) {
          console.error('Failed to parse error response:', e);
          set(
            produce((state) => {
              state.isLoadingById.set(id, false);
            })
          );
        }
      } else {
        set(
          produce((state) => {
            state.isLoadingById.set(id, false);
          })
        );
      }
    }
  },
}));

function extractInputKeysFromSchema(schema: JsonSchema | undefined): string[] | undefined {
  if (!schema || !('properties' in schema)) return undefined;

  const properties = schema.properties;
  if (!properties) return undefined;

  return Object.keys(properties);
}

function fixSchemaFormat(schema: JsonSchema | undefined): JsonSchema | undefined {
  return {
    ...schema,
    format: 'messages',
  };
}

function removePropertiesKeyIfThereAreNotPropertiesFromSchema(schema: JsonSchema | undefined): JsonSchema | undefined {
  if (!schema) return schema;
  const newSchema = { ...schema } as JsonSchema;

  if (!('properties' in newSchema)) return schema;
  const properties = newSchema.properties;

  if (!properties || Object.keys(properties).length === 0) {
    unset(newSchema, 'properties');
    return newSchema;
  }

  return schema;
}

export const useOrExtractTemplete = (
  tenant: TenantID | undefined,
  taskId: TaskID,
  schemaId: number | undefined,
  messages: ProxyMessage[] | undefined,
  inputSchema: JsonSchema | undefined,
  historyId: string | undefined
) => {
  const id = useMemo(() => {
    return `${tenant}-${taskId}-${schemaId}-${historyId}`;
  }, [tenant, taskId, schemaId, historyId]);

  const isLoading = useExtractTemplete((state) => state.isLoadingById.get(id));
  const extractedSchema = useExtractTemplete((state) => state.schemaById.get(id));
  const error = useExtractTemplete((state) => state.errorById.get(id));

  const [typeSchema, setTypeSchema] = useState<JsonSchema | undefined>(undefined);

  const schema = useMemo(() => {
    if (!extractedSchema || messages?.length === 0 || !messages) return inputSchema;
    const fixedSchema = fixSchemaFormat(extractedSchema);
    const mergedSchema = mergeSchemaTypesAndDefs(fixedSchema, typeSchema);
    const resultSchema = removePropertiesKeyIfThereAreNotPropertiesFromSchema(mergedSchema);
    return resultSchema;
  }, [extractedSchema, inputSchema, messages, typeSchema]);

  const extract = useExtractTemplete((state) => state.extract);

  const inputVariblesKeys = useMemo(() => {
    return extractInputKeysFromSchema(schema);
  }, [schema]);

  const abortControllerRef = useRef<AbortController | undefined>(undefined);

  const performExtract = useCallback(async () => {
    if (!messages || messages.length === 0) {
      return;
    }

    abortControllerRef.current?.abort();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    extract(id, tenant, taskId, messages ?? [], inputSchema, abortController.signal);
  }, [extract, tenant, taskId, messages, inputSchema, id]);

  useEffect(() => {
    if (!messages || messages.length === 0) {
      return;
    }

    abortControllerRef.current?.abort();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const debouncedExtract = debounce(() => {
      extract(id, tenant, taskId, messages, inputSchema, abortController.signal);
    }, 500);

    debouncedExtract();

    return () => {
      debouncedExtract.cancel();
      abortController.abort();
    };
  }, [extract, tenant, taskId, messages, inputSchema, id]);

  const areThereChangesInInputSchema = useMemo(() => {
    if (!schema || !inputSchema) return false;
    return !areSchemasEquivalent(schema, inputSchema);
  }, [schema, inputSchema]);

  return {
    isLoading: isLoading,
    schema,
    setSchema: setTypeSchema,
    inputVariblesKeys,
    error,
    areThereChangesInInputSchema,
    performExtract,
  };
};
