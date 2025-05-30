import { useCallback, useEffect, useState } from 'react';
import { StreamedChunk } from '@/types/task_run';
import { RunResponseStreamChunk } from '@/types/workflowAI';

export function useProxyStreamedChunks(
  taskRunId1: string | undefined,
  taskRunId2: string | undefined,
  taskRunId3: string | undefined
) {
  const [streamedChunks, setStreamedChunks] = useState<(StreamedChunk | undefined)[]>(() => []);

  const setStreamedChunk = useCallback((index: number, message: RunResponseStreamChunk | undefined) => {
    setStreamedChunks((prev) => {
      const chunks = [...prev];
      if (message) {
        chunks[index] = {
          output: message?.task_output,
          toolCalls: message?.tool_calls ?? undefined,
          reasoningSteps: message?.reasoning_steps ?? undefined,
        };
      } else {
        chunks[index] = undefined;
      }
      return chunks;
    });
  }, []);

  useEffect(() => {
    if (taskRunId1) {
      setStreamedChunk(0, undefined);
    }
  }, [setStreamedChunk, taskRunId1]);

  useEffect(() => {
    if (taskRunId2) {
      setStreamedChunk(1, undefined);
    }
  }, [setStreamedChunk, taskRunId2]);

  useEffect(() => {
    if (taskRunId3) {
      setStreamedChunk(2, undefined);
    }
  }, [setStreamedChunk, taskRunId3]);

  return { streamedChunks, setStreamedChunk };
}
