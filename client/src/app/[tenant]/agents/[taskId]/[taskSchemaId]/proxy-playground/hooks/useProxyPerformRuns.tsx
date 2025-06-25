import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useMap } from 'usehooks-ts';
import { useAIModels } from '@/store/ai_models';
import { useOrganizationSettings } from '@/store/organization_settings';
import { usePlaygroundChatStore } from '@/store/playgroundChatStore';
import { useProxyChatCompletition } from '@/store/proxyChatCompletition';
import { useTasks } from '@/store/task';
import { useTaskSchemas } from '@/store/task_schemas';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { StreamError } from '@/types/errors';
import { JsonSchema } from '@/types/json_schema';
import { GeneralizedTaskInput } from '@/types/task_run';
import { ProxyMessage, ToolKind, Tool_Output } from '@/types/workflowAI';
import { useFetchTaskRunUntilCreated } from '../../playground/hooks/useFetchTaskRunUntilCreated';
import { PlaygroundModels } from '../../playground/hooks/utils';
import { cleanChunkOutput, removeInputEntriesNotMatchingSchemaAndKeepMessages } from '../utils';
import { AdvancedSettings } from './useProxyPlaygroundSearchParams';
import { useProxyStreamedChunks } from './useProxyStreamedChunks';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  schemaId: TaskSchemaID;
  variantId: string | undefined;
  taskRunId1: string | undefined;
  taskRunId2: string | undefined;
  taskRunId3: string | undefined;
  setTaskRunId: (index: number, runId: string | undefined) => void;
  hiddenModelColumns: number[];
  areThereChangesInInputSchema: boolean;
  extractedInputSchema: JsonSchema | undefined;
  outputSchema: JsonSchema | undefined;
  setSchemaId: (schemaId: TaskSchemaID) => void;
  changeURLSchemaId: (schemaId: TaskSchemaID, scrollToBottom?: boolean) => void;
  proxyMessages: ProxyMessage[] | undefined;
  proxyToolCalls: (ToolKind | Tool_Output)[] | undefined;
  outputModels: PlaygroundModels;
  input: GeneralizedTaskInput | undefined;
  setScheduledPlaygroundStateMessage: (message: string | undefined) => void;
  advancedSettings: AdvancedSettings;
};

export function useProxyPerformRuns(props: Props) {
  const {
    taskRunId1,
    taskRunId2,
    taskRunId3,
    setTaskRunId,
    hiddenModelColumns,
    areThereChangesInInputSchema,
    extractedInputSchema,
    outputSchema,
    schemaId,
    variantId,
    tenant,
    taskId,
    setSchemaId,
    changeURLSchemaId,
    proxyMessages,
    proxyToolCalls,
    outputModels,
    input,
    setScheduledPlaygroundStateMessage,
    advancedSettings,
  } = props;

  const variantIdRef = useRef<string | undefined>(variantId);
  variantIdRef.current = variantId;
  useEffect(() => {
    variantIdRef.current = variantId;
  }, [variantId]);

  const schemaIdRef = useRef<TaskSchemaID>(schemaId);
  schemaIdRef.current = schemaId;
  useEffect(() => {
    schemaIdRef.current = schemaId;
  }, [schemaId]);

  const outputSchemaRef = useRef<JsonSchema | undefined>(outputSchema);
  outputSchemaRef.current = outputSchema;
  useEffect(() => {
    outputSchemaRef.current = outputSchema;
  }, [outputSchema]);

  const outputModelsRef = useRef<PlaygroundModels>(outputModels);
  outputModelsRef.current = outputModels;
  useEffect(() => {
    outputModelsRef.current = outputModels;
  }, [outputModels]);

  const inputRef = useRef<GeneralizedTaskInput | undefined>(input);
  inputRef.current = input;
  useEffect(() => {
    inputRef.current = input;
  }, [input]);

  const proxyMessagesRef = useRef<ProxyMessage[] | undefined>(proxyMessages);
  proxyMessagesRef.current = proxyMessages;
  useEffect(() => {
    proxyMessagesRef.current = proxyMessages;
  }, [proxyMessages]);

  const proxyToolCallsRef = useRef<(ToolKind | Tool_Output)[] | undefined>(proxyToolCalls);
  proxyToolCallsRef.current = proxyToolCalls;
  useEffect(() => {
    proxyToolCallsRef.current = proxyToolCalls;
  }, [proxyToolCalls]);

  const areThereChangesInInputSchemaRef = useRef<boolean>(areThereChangesInInputSchema);
  areThereChangesInInputSchemaRef.current = areThereChangesInInputSchema;
  useEffect(() => {
    areThereChangesInInputSchemaRef.current = areThereChangesInInputSchema;
  }, [areThereChangesInInputSchema]);

  const extractedInputSchemaRef = useRef<JsonSchema | undefined>(extractedInputSchema);
  extractedInputSchemaRef.current = extractedInputSchema;
  useEffect(() => {
    extractedInputSchemaRef.current = extractedInputSchema;
  }, [extractedInputSchema]);

  const advancedSettingsRef = useRef<AdvancedSettings | undefined>(advancedSettings);
  advancedSettingsRef.current = advancedSettings;
  useEffect(() => {
    advancedSettingsRef.current = advancedSettings;
  }, [advancedSettings]);

  const { streamedChunks, setStreamedChunk } = useProxyStreamedChunks(taskRunId1, taskRunId2, taskRunId3);
  const [inProgressIndexes, setInProgressIndexes] = useState<number[]>([]);
  const [errorsForModels, { set: setModelError, remove: removeModelError }] = useMap<string, Error>(
    new Map<string, Error>()
  );

  const setInProgress = useCallback((index: number, inProgress: boolean) => {
    setInProgressIndexes((prev) => {
      if (inProgress) {
        if (!prev.includes(index)) {
          return [...prev, index];
        }
      } else {
        return prev.filter((i) => i !== index);
      }
      return prev;
    });
  }, []);

  const defaultIndexes = useMemo(() => {
    return [0, 1, 2].filter((index) => !hiddenModelColumns.includes(index));
  }, [hiddenModelColumns]);

  const updateTaskSchema = useTasks((state) => state.updateTaskSchema);
  const fetchTaskSchema = useTaskSchemas((state) => state.fetchTaskSchema);
  const fetchModels = useAIModels((state) => state.fetchSchemaModels);
  const fetchTaskRunUntilCreated = useFetchTaskRunUntilCreated();
  const fetchOrganizationSettings = useOrganizationSettings((state) => state.fetchOrganizationSettings);
  const { performRun: performRunProxy } = useProxyChatCompletition();

  const checkAndUpdateSchemaIfNeeded = useCallback(async () => {
    if (!areThereChangesInInputSchemaRef.current || !outputSchemaRef.current || !extractedInputSchemaRef.current) {
      return undefined;
    }

    const updatedTask = await updateTaskSchema(tenant, taskId, {
      input_schema: extractedInputSchemaRef.current as Record<string, unknown>,
      output_schema: outputSchemaRef.current as Record<string, unknown>,
    });

    const newSchema = `${updatedTask.schema_id}` as TaskSchemaID;

    if (newSchema === schemaIdRef.current) {
      return undefined;
    }

    await fetchTaskSchema(tenant, taskId, newSchema);
    await fetchModels(tenant, taskId, newSchema);

    setSchemaId(newSchema);

    return newSchema;
  }, [updateTaskSchema, tenant, taskId, setSchemaId, fetchTaskSchema, fetchModels]);

  const abortControllerRun0 = useRef<AbortController | null>(null);
  const abortControllerRun1 = useRef<AbortController | null>(null);
  const abortControllerRun2 = useRef<AbortController | null>(null);

  const findAbortController = useCallback((index: number) => {
    switch (index) {
      case 0:
        return abortControllerRun0;
      case 1:
        return abortControllerRun1;
      case 2:
        return abortControllerRun2;
      default:
        return null;
    }
  }, []);

  const setAbortController = useCallback((index: number, abortController: AbortController) => {
    switch (index) {
      case 0:
        abortControllerRun0.current = abortController;
        break;
      case 1:
        abortControllerRun1.current = abortController;
        break;
      case 2:
        abortControllerRun2.current = abortController;
        break;
    }
  }, []);

  const performRun = useCallback(
    async (index: number) => {
      const variantId = variantIdRef.current;
      if (variantId === undefined) {
        return;
      }

      const model = outputModelsRef.current[index];
      if (!model) {
        return;
      }

      if (model) {
        removeModelError(model);
      }

      const oldAbortController = findAbortController(index);
      oldAbortController?.current?.abort();

      const abortController = new AbortController();
      setAbortController(index, abortController);

      const clean = () => {
        setTaskRunId(index, undefined);
        setStreamedChunk(index, undefined);
        setInProgress(index, false);
      };

      try {
        const cleanedInput =
          removeInputEntriesNotMatchingSchemaAndKeepMessages(
            inputRef.current as Record<string, unknown> | undefined,
            extractedInputSchemaRef.current
          ) ?? {};

        const runId = await performRunProxy(
          taskId,
          variantId,
          model,
          cleanedInput,
          proxyMessagesRef.current ?? [],
          advancedSettingsRef.current,
          proxyToolCallsRef.current,
          (runId, output) => {
            if (abortController.signal.aborted) {
              clean();
              return;
            }

            const cleanedChunkOutput = cleanChunkOutput(output);

            setStreamedChunk(index, {
              id: runId,
              task_output: cleanedChunkOutput,
              tool_call_requests: null,
              reasoning_steps: null,
              tool_calls: null,
            });
          },
          abortController.signal
        );

        if (abortController.signal.aborted) {
          clean();
          return;
        }

        await fetchTaskRunUntilCreated(tenant, taskId, runId);

        clean();
        setTaskRunId(index, runId);
      } catch (error: unknown) {
        if (abortController.signal.aborted) {
          clean();
          return;
        }

        const model = outputModelsRef.current[index];
        if (error instanceof Error && !!model) {
          setModelError(model, error);
        }

        if (
          error instanceof StreamError &&
          !!error.extra &&
          'runId' in error.extra &&
          typeof error.extra.runId === 'string'
        ) {
          await fetchTaskRunUntilCreated(tenant, taskId, error.extra.runId);
          clean();
          setTaskRunId(index, error.extra.runId);
          return;
        }

        console.error(error);
        clean();
      }
    },
    [
      findAbortController,
      setAbortController,
      tenant,
      taskId,
      setTaskRunId,
      setStreamedChunk,
      setInProgress,
      fetchTaskRunUntilCreated,
      setModelError,
      removeModelError,
      performRunProxy,
    ]
  );

  const stopRun = useCallback(
    (index: number) => {
      const abortController = findAbortController(index);
      abortController?.current?.abort();
    },
    [findAbortController]
  );

  const stopAllRuns = useCallback(() => {
    abortControllerRun0.current?.abort();
    abortControllerRun1.current?.abort();
    abortControllerRun2.current?.abort();
  }, []);

  const { getScheduledPlaygroundStateMessageToSendAfterRuns } = usePlaygroundChatStore();

  const performRuns = useCallback(
    async (indexes?: number[]) => {
      if (variantIdRef.current === undefined) {
        return;
      }

      const indexesToRun = indexes ?? defaultIndexes;

      if (indexesToRun.length === 0) {
        return;
      }

      indexesToRun.forEach((index) => {
        setInProgress(index, true);
        setTaskRunId(index, undefined);
        setStreamedChunk(index, undefined);
      });

      const newSchema = await checkAndUpdateSchemaIfNeeded();
      await Promise.all(indexesToRun.map((index) => performRun(index)));
      if (newSchema) {
        await fetchModels(tenant, taskId, newSchema);
      }
      await fetchOrganizationSettings();

      if (newSchema) {
        // Timeout set to prevent blinking when refreashing the inputs
        setTimeout(() => {
          changeURLSchemaId(newSchema, true);
        }, 500);
      }

      const message = getScheduledPlaygroundStateMessageToSendAfterRuns();
      if (message) {
        setScheduledPlaygroundStateMessage(message);
      }
    },
    [
      setTaskRunId,
      setStreamedChunk,
      setInProgress,
      defaultIndexes,
      checkAndUpdateSchemaIfNeeded,
      performRun,
      changeURLSchemaId,
      fetchOrganizationSettings,
      fetchModels,
      tenant,
      taskId,
      getScheduledPlaygroundStateMessageToSendAfterRuns,
      setScheduledPlaygroundStateMessage,
    ]
  );

  const areTasksRunning = useMemo(() => {
    return inProgressIndexes.length > 0;
  }, [inProgressIndexes]);

  return {
    performRuns,
    stopRun,
    areTasksRunning,
    streamedChunks,
    inProgressIndexes,
    errorsForModels,
    stopAllRuns,
  };
}
