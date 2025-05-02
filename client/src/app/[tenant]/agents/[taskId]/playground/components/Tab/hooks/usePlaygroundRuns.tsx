import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { RequestError } from '@/lib/api/client';
import { useCompatibleAIModels } from '@/lib/hooks/useCompatibleAIModels';
import { useTasks } from '@/store/task';
import { useVersions } from '@/store/versions';
import { GeneralizedTaskInput, TaskOutput, ToolCallPreview, toolCallsFromRunV1 } from '@/types';
import { TenantID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { StreamError } from '@/types/errors';
import {
  MajorVersion,
  ReasoningStep,
  RunRequest,
  RunResponseStreamChunk,
  RunV1,
  TaskGroupProperties_Input,
} from '@/types/workflowAI';
import { useFetchTaskRunUntilCreated } from './useFetchTaskRunUntilCreated';

export function usePlaygroundRuns(
  tenant: TenantID | undefined,
  taskId: TaskID,
  schemaId: TaskSchemaID,
  variantId: string | undefined,
  runId: string | undefined,
  model: string | undefined,
  instructions: string,
  temperature: number,
  input: GeneralizedTaskInput | undefined,
  onSelectModelRun: (runId: string | undefined) => void,
  run: RunV1 | undefined,
  majorVersion: MajorVersion | undefined
) {
  const hash = useMemo(() => {
    const inputString = JSON.stringify(input);
    return `${tenant}-${taskId}-${schemaId}-${variantId}-${model}-${instructions}-${temperature}-${inputString}-${majorVersion?.major}`;
  }, [tenant, taskId, schemaId, variantId, model, instructions, temperature, input, majorVersion?.major]);

  const hashRef = useRef(hash);
  hashRef.current = hash;

  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined);

  const [streamedToolCalls, setStreamedToolCalls] = useState<ToolCallPreview[] | undefined>(undefined);
  const [streamedReasoningSteps, setStreamedReasoningSteps] = useState<ReasoningStep[] | undefined>(undefined);
  const [streamedOutput, setStreamedOutput] = useState<TaskOutput | undefined>(undefined);

  const [isRunning, setIsRunning] = useState(false);

  const { compatibleModels } = useCompatibleAIModels({
    tenant,
    taskId,
    taskSchemaId: schemaId,
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  const createVersion = useVersions((state) => state.createVersion);
  const runTask = useTasks((state) => state.runTask);
  const fetchTaskRunUntilCreated = useFetchTaskRunUntilCreated();

  const updateStreamedMessage = useCallback((message: RunResponseStreamChunk | undefined) => {
    if (!message) {
      return;
    }

    const output = message.task_output;
    const toolCalls = message.tool_calls;
    const reasoningSteps = message.reasoning_steps ?? undefined;

    setStreamedOutput(output);
    setStreamedToolCalls(toolCalls ?? undefined);
    setStreamedReasoningSteps(reasoningSteps);
  }, []);

  const onClean = useCallback(() => {
    setErrorMessage(undefined);
    setStreamedToolCalls(undefined);
    setStreamedReasoningSteps(undefined);
    setStreamedOutput(undefined);
    setIsRunning(false);
  }, [setErrorMessage]);

  const onRun = useCallback(async () => {
    abortControllerRef.current?.abort();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    if (!model || !input) {
      return;
    }

    onClean();
    onSelectModelRun(undefined);
    setIsRunning(true);
    const properties: TaskGroupProperties_Input = {
      model,
      instructions,
      temperature,
      task_variant_id: variantId,
    };

    let versionId: string | undefined;
    try {
      const response = await createVersion(tenant, taskId, schemaId, {
        properties,
      });
      versionId = response.id;
    } catch (error) {
      setIsRunning(false);

      if (abortController.signal.aborted) {
        onClean();
        return;
      }

      if (error instanceof RequestError) {
        const message = await error.humanReadableMessage();
        setErrorMessage(message);
        return;
      } else {
        setErrorMessage('Failed to create version');
        return;
      }
    }

    if (abortController.signal.aborted || !versionId) {
      setIsRunning(false);
      return;
    }

    const body: RunRequest = {
      task_input: input as Record<string, unknown>,
      version: versionId,
    };

    if (temperature !== 0) {
      body.use_cache = 'never';
    }

    try {
      const result = await runTask({
        tenant,
        taskId,
        taskSchemaId: schemaId,
        body,
        onMessage: (message) => {
          if (abortController.signal.aborted) {
            onClean();
            return;
          }
          updateStreamedMessage(message);
        },
        signal: abortController.signal,
      });

      await fetchTaskRunUntilCreated(tenant, taskId, result.id);

      if (abortController.signal.aborted) {
        return;
      }

      onSelectModelRun(result.id);
      setIsRunning(false);
    } catch (error) {
      if (abortController.signal.aborted) {
        onClean();
        setIsRunning(false);
        return;
      }

      if (
        error instanceof StreamError &&
        !!error.extra &&
        'runId' in error.extra &&
        typeof error.extra.runId === 'string'
      ) {
        const runId = error.extra.runId;
        await fetchTaskRunUntilCreated(tenant, taskId, runId);

        if (abortController.signal.aborted) {
          return;
        }

        onSelectModelRun(runId);
      }

      if (error instanceof RequestError) {
        const message = await error.humanReadableMessage();
        setErrorMessage(message);
        setIsRunning(false);
        return;
      } else {
        setErrorMessage('Failed to create version');
        setIsRunning(false);
        return;
      }
    }
  }, [
    model,
    instructions,
    temperature,
    variantId,
    createVersion,
    schemaId,
    taskId,
    tenant,
    input,
    runTask,
    updateStreamedMessage,
    onSelectModelRun,
    onClean,
    fetchTaskRunUntilCreated,
  ]);

  const onStopRun = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  const wasRunSuccessfull = useMemo(() => {
    return !isRunning && !errorMessage && !!runId;
  }, [isRunning, errorMessage, runId]);

  const toolCalls: ToolCallPreview[] | undefined = useMemo(() => {
    if (!run) {
      return streamedToolCalls;
    }

    return toolCallsFromRunV1(run);
  }, [run, streamedToolCalls]);

  const reasoningSteps: ReasoningStep[] | undefined = useMemo(() => {
    if (!run) {
      return streamedReasoningSteps;
    }

    return run?.reasoning_steps ?? undefined;
  }, [run, streamedReasoningSteps]);

  const output: TaskOutput | undefined = useMemo(() => {
    if (!run) {
      return streamedOutput;
    }

    return run?.task_output;
  }, [run, streamedOutput]);

  useEffect(() => {
    onStopRun();
    onClean();
  }, [hash, onClean, onStopRun]);

  return {
    compatibleModels: compatibleModels.length > 0 ? compatibleModels : undefined,
    onRun,
    onStopRun,
    isRunning,
    errorMessage,
    wasRunSuccessfull,
    toolCalls,
    reasoningSteps,
    output,
  };
}
