import { useCallback, useMemo } from 'react';
import { requiresFileSupport } from '@/lib/schemaFileUtils';
import { InitInputFromSchemaMode } from '@/lib/schemaUtils';
import { initInputFromSchema } from '@/lib/schemaUtils';
import { useOrFetchTaskSchema } from '@/store';
import { TaskID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { TaskSchemaResponseWithSchema } from '@/types/task';
import { MajorVersion } from '@/types/workflowAI';
import { useInputGenerator } from './useInputGenerator';
import { usePlaygroundInputHistory } from './usePlaygroundInputHistory';

export function usePlaygroundInput(
  tenant: TenantID | undefined,
  taskId: TaskID,
  tabId: string | undefined,
  majorVersion: MajorVersion | undefined,
  newestSchema: TaskSchemaResponseWithSchema | undefined
) {
  const majorSchemaId = majorVersion ? (`${majorVersion?.schema_id}` as TaskSchemaID) : undefined;
  const { taskSchema: majorSchema } = useOrFetchTaskSchema(tenant, taskId, majorSchemaId);

  const newestSchemaId = `${newestSchema?.schema_id}` as TaskSchemaID;

  const schema = majorSchema ?? newestSchema;
  const schemaId = majorSchemaId ?? newestSchemaId;
  const variantId = majorVersion?.properties.task_variant_id ?? newestSchema?.latest_variant_id ?? undefined;

  const inputSchema = schema?.input_schema.json_schema;
  const outputSchema = schema?.output_schema.json_schema;

  const isInputGenerationSupported = useMemo(() => {
    if (!schema) return false;
    return !requiresFileSupport(schema.input_schema.json_schema, schema.input_schema.json_schema.$defs);
  }, [schema]);

  const voidInput = useMemo(() => {
    if (!inputSchema) return undefined;
    return initInputFromSchema(inputSchema, inputSchema.$defs, InitInputFromSchemaMode.VOID);
  }, [inputSchema]);

  const {
    input,
    setInput,
    saveToHistory,
    moveToPrevious: onMoveToPreviousInput,
    moveToNext: onMoveToNextInput,
  } = usePlaygroundInputHistory(tenant, taskId, schemaId, tabId, isInputGenerationSupported);

  const { onGenerateInput, onStopGeneratingInput, isGenerating } = useInputGenerator(
    tenant,
    taskId,
    schemaId,
    setInput,
    voidInput
  );

  const onGenerateInputAndSaveToHistory = useCallback(async () => {
    const input = await onGenerateInput();
    if (input) {
      saveToHistory(input);
    }
  }, [onGenerateInput, saveToHistory]);

  return {
    schemaId,
    variantId,
    inputSchema,
    outputSchema,
    isInputGenerationSupported,
    isGeneratingInput: isGenerating,
    input,
    setInput,
    onGenerateInput: onGenerateInputAndSaveToHistory,
    onStopGeneratingInput,
    voidInput,
    onMoveToPreviousInput,
    onMoveToNextInput,
  };
}
