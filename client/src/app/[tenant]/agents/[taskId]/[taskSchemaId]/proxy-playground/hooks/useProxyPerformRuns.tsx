import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useMap } from 'usehooks-ts';
import { useAIModels } from '@/store/ai_models';
import { useOrganizationSettings } from '@/store/organization_settings';
import { usePlaygroundChatStore } from '@/store/playgroundChatStore';
import { useTasks } from '@/store/task';
import { useTaskSchemas } from '@/store/task_schemas';
import { useVersions } from '@/store/versions';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { StreamError } from '@/types/errors';
import { JsonSchema } from '@/types/json_schema';
import { GeneralizedTaskInput } from '@/types/task_run';
import { ProxyMessage, RunRequest, TaskGroupProperties_Input, ToolKind, Tool_Output } from '@/types/workflowAI';
import { useFetchTaskRunUntilCreated } from '../../playground/hooks/useFetchTaskRunUntilCreated';
import { PlaygroundModels } from '../../playground/hooks/utils';
import { removeInputEntriesNotMatchingSchemaAndKeepMessages } from '../utils';
import { useProxyStreamedChunks } from './useProxyStreamedChunks';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  schemaId: TaskSchemaID;
  taskRunId1: string | undefined;
  taskRunId2: string | undefined;
  taskRunId3: string | undefined;
  setTaskRunId: (index: number, runId: string | undefined) => void;
  hiddenModelColumns: number[];
  areThereChangesInInputSchema: boolean;
  extractedInputSchema: JsonSchema | undefined;
  outputSchema: JsonSchema;
  setSchemaId: (schemaId: TaskSchemaID) => void;
  changeURLSchemaId: (schemaId: TaskSchemaID, scrollToBottom?: boolean) => void;
  proxyMessages: ProxyMessage[] | undefined;
  proxyToolCalls: (ToolKind | Tool_Output)[] | undefined;
  outputModels: PlaygroundModels;
  temperature: number | undefined;
  input: GeneralizedTaskInput | undefined;
  setScheduledPlaygroundStateMessage: (message: string | undefined) => void;
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
    tenant,
    taskId,
    setSchemaId,
    changeURLSchemaId,
    proxyMessages,
    proxyToolCalls,
    outputModels,
    temperature,
    input,
    setScheduledPlaygroundStateMessage,
  } = props;

  const schemaIdRef = useRef<TaskSchemaID>(schemaId);
  schemaIdRef.current = schemaId;
  useEffect(() => {
    schemaIdRef.current = schemaId;
  }, [schemaId]);

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

  const temperatureRef = useRef<number | undefined>(temperature);
  temperatureRef.current = temperature;
  useEffect(() => {
    temperatureRef.current = temperature;
  }, [temperature]);

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
  const fetchModels = useAIModels((state) => state.fetchModels);
  const createVersion = useVersions((state) => state.createVersion);
  const runTask = useTasks((state) => state.runTask);
  const fetchTaskRunUntilCreated = useFetchTaskRunUntilCreated();
  const fetchOrganizationSettings = useOrganizationSettings((state) => state.fetchOrganizationSettings);

  const checkAndUpdateSchemaIfNeeded = useCallback(async () => {
    if (!areThereChangesInInputSchemaRef.current) {
      return undefined;
    }

    const updatedTask = await updateTaskSchema(tenant, taskId, {
      input_schema: extractedInputSchemaRef.current as Record<string, unknown>,
      output_schema: outputSchema as Record<string, unknown>,
    });

    const newSchema = `${updatedTask.schema_id}` as TaskSchemaID;

    if (newSchema === schemaIdRef.current) {
      return undefined;
    }

    await fetchTaskSchema(tenant, taskId, newSchema);
    await fetchModels(tenant, taskId, newSchema);

    setSchemaId(newSchema);

    return newSchema;
  }, [outputSchema, updateTaskSchema, tenant, taskId, setSchemaId, fetchTaskSchema, fetchModels]);

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
      const model = outputModelsRef.current[index];
      if (model) {
        removeModelError(model);
      }

      const oldAbortController = findAbortController(index);
      oldAbortController?.current?.abort();

      const abortController = new AbortController();
      setAbortController(index, abortController);

      const properties: TaskGroupProperties_Input = {
        model: outputModelsRef.current[index],
        temperature: temperatureRef.current,
        enabled_tools: proxyToolCallsRef.current,
        messages: proxyMessagesRef.current,
      };

      const clean = () => {
        setTaskRunId(index, undefined);
        setStreamedChunk(index, undefined);
        setInProgress(index, false);
      };

      try {
        const { id: versionId } = await createVersion(tenant, taskId, schemaIdRef.current, {
          properties,
        });

        if (abortController.signal.aborted) {
          clean();
          return;
        }

        // TODO: remove this once the bug on with the messages when inputs are set are not taken into account is fixed
        //const useCache = !!temperatureRef.current && temperatureRef.current === 0 ? 'never' : undefined;
        const useCache = 'never';

        const cleanedInput = removeInputEntriesNotMatchingSchemaAndKeepMessages(
          inputRef.current as Record<string, unknown>,
          extractedInputSchemaRef.current
        );

        const request: RunRequest = {
          task_input: cleanedInput,
          version: versionId,
          use_cache: useCache,
        };

        const { id: runId } = await runTask({
          tenant,
          taskId,
          taskSchemaId: schemaIdRef.current,
          body: request,
          onMessage: (message) => {
            if (abortController.signal.aborted) {
              clean();
              return;
            }
            setStreamedChunk(index, message);
          },
          signal: abortController.signal,
        });

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
      createVersion,
      tenant,
      taskId,
      setTaskRunId,
      setStreamedChunk,
      setInProgress,
      runTask,
      fetchTaskRunUntilCreated,
      setModelError,
      removeModelError,
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
      await fetchModels(tenant, taskId, newSchema as TaskSchemaID);
      await fetchOrganizationSettings();

      if (newSchema) {
        changeURLSchemaId(newSchema, true);
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
