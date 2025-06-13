import { isEmpty, isEqual } from 'lodash';
import { useCallback, useMemo } from 'react';
import { GeneralizedTaskInput, StreamedChunk } from '@/types';
import { ToolCallPreview } from '@/types';
import { toolCallsFromRunV1 } from '@/types/utils';
import { ReasoningStep, RunV1 } from '@/types/workflowAI';

export type TaskRunner = {
  loading: boolean;
  streamingOutput: Record<string, unknown> | undefined;
  toolCalls: Array<ToolCallPreview> | undefined;
  reasoningSteps: ReasoningStep[] | undefined;
  data: RunV1 | undefined;
  inputStatus: 'unprocessed' | 'processed';
  execute: () => void;
  cancel: () => void;
};

type Props = {
  taskRuns: (RunV1 | undefined)[];
  playgroundOutputsLoading: [boolean, boolean, boolean];
  streamedChunks: (StreamedChunk | undefined)[];
  handleRunTask: (index: number) => Promise<void>;
  cancelRunTask: (index: number) => void;
  generatedInput: GeneralizedTaskInput | undefined;
};

function useInputMatchStatus(
  taskRunInput: GeneralizedTaskInput | undefined,
  formInput: GeneralizedTaskInput | undefined
) {
  return useMemo(() => {
    if (taskRunInput === undefined || formInput === undefined) {
      return 'unprocessed';
    }
    // We need to remove undefined values from the generated input
    const processedFormInput = JSON.parse(JSON.stringify(formInput));
    if (isEqual(taskRunInput, processedFormInput)) {
      return 'processed';
    }
    return 'unprocessed';
  }, [taskRunInput, formInput]);
}

function extractToolCalls(streamedChunk: StreamedChunk | undefined, final: RunV1 | undefined) {
  const taskRunToolCalls = toolCallsFromRunV1(final);
  if (!!taskRunToolCalls && taskRunToolCalls.length > 0) {
    return taskRunToolCalls;
  }
  return streamedChunk?.toolCalls;
}

function extractReasoningSteps(streamedChunk: StreamedChunk | undefined, final: RunV1 | undefined) {
  const taskRunReasoningSteps = final?.reasoning_steps;
  if (!isEmpty(taskRunReasoningSteps)) {
    return taskRunReasoningSteps;
  }
  return streamedChunk?.reasoningSteps ?? undefined;
}

function useTaskRunner(index: 0 | 1 | 2, props: Props) {
  const { taskRuns, playgroundOutputsLoading, streamedChunks, handleRunTask, cancelRunTask, generatedInput } = props;

  const inputStatus = useInputMatchStatus(taskRuns[index]?.task_input, generatedInput);

  const execute = useCallback(async () => {
    await handleRunTask(index);
  }, [handleRunTask, index]);

  const cancel = useCallback(() => {
    cancelRunTask(index);
  }, [cancelRunTask, index]);

  const loading = playgroundOutputsLoading[index];
  const streamedChunk = streamedChunks[index];
  const data = taskRuns[index];

  return useMemo<TaskRunner>(
    () => ({
      loading,
      streamingOutput: streamedChunk?.output,
      toolCalls: extractToolCalls(streamedChunk, data),
      data,
      inputStatus,
      execute,
      cancel,
      reasoningSteps: extractReasoningSteps(streamedChunk, data) ?? undefined,
    }),
    [loading, streamedChunk, data, inputStatus, execute, cancel]
  );
}

export function useTaskRunners(props: Props) {
  const taskRunner0 = useTaskRunner(0, props);
  const taskRunner1 = useTaskRunner(1, props);
  const taskRunner2 = useTaskRunner(2, props);

  return useMemo<[TaskRunner, TaskRunner, TaskRunner]>(
    () => [taskRunner0, taskRunner1, taskRunner2],
    [taskRunner0, taskRunner1, taskRunner2]
  );
}
