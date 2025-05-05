import { captureException } from '@sentry/nextjs';
import { useCallback, useRef, useState } from 'react';
import { displayErrorToaster, displaySuccessToaster } from '@/components/ui/Sonner';
import { ToolCallName, usePlaygroundChatStore } from '@/store/playgroundChatStore';
import { ImproveVersionResponse, useTasks } from '@/store/task';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { ImproveVersionRequest, ToolKind } from '@/types/workflowAI';

export function useImproveInstructions(
  tenant: TenantID | undefined,
  taskId: TaskID,
  taskSchemaId: TaskSchemaID,
  variantId: string | undefined,
  instructions: string,
  setInstructions: (instructions: string) => void,
  setChangelog: (changelog: string[] | undefined) => void
) {
  const improveVersion = useTasks((state) => state.improveVersion);

  const [oldInstructions, setOldInstructions] = useState<string | undefined>(undefined);

  const resetOldInstructions = useCallback(() => {
    setOldInstructions(undefined);
  }, []);

  const instructionsRef = useRef(instructions);
  instructionsRef.current = instructions;

  const [isLoading, setIsLoading] = useState(false);
  const { markToolCallAsDone, cancelToolCall } = usePlaygroundChatStore();

  const abortControllerRef = useRef<AbortController | undefined>(undefined);

  const improveInstructions = useCallback(
    async (text: string, runId: string | undefined) => {
      if (!instructionsRef.current) {
        return;
      }

      abortControllerRef.current?.abort();
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      try {
        const onMessage = (message: ImproveVersionResponse) => {
          if (abortController.signal.aborted) {
            return;
          }
          const { improved_properties, changelog } = message;
          setChangelog(changelog);
          setIsLoading(true);
          const newInstructions = improved_properties.instructions || '';
          setInstructions(newInstructions);
        };

        setOldInstructions(instructionsRef.current);
        setIsLoading(true);

        const payload: ImproveVersionRequest = {
          run_id: runId,
          user_evaluation: text,
          variant_id: variantId,
          instructions: instructionsRef.current,
        };

        const { improved_properties, changelog } = await improveVersion(
          tenant,
          taskId,
          payload,
          onMessage,
          abortController.signal
        );

        setChangelog(changelog);
        const newInstructions = improved_properties.instructions || '';
        setInstructions(newInstructions);
        displaySuccessToaster('Updated Instructions generated. Rerunning AI agent...');

        setIsLoading(false);
        markToolCallAsDone(taskId, ToolCallName.IMPROVE_AGENT_INSTRUCTIONS);
      } catch (error) {
        cancelToolCall(ToolCallName.IMPROVE_AGENT_INSTRUCTIONS);
        setIsLoading(false);
        captureException(error);
        if (!abortController.signal.aborted) {
          return;
        }
        displayErrorToaster('Failed to improve AI agent run version - Please try again');
      }
    },
    [improveVersion, taskId, tenant, setInstructions, setChangelog, variantId, cancelToolCall, markToolCallAsDone]
  );

  const updateTaskInstructions = useTasks((state) => state.updateTaskInstructions);

  const onToolsChange = useCallback(
    async (tools: ToolKind[]) => {
      abortControllerRef.current?.abort();
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      setOldInstructions(instructionsRef.current);
      setIsLoading(true);

      try {
        const data = await updateTaskInstructions(
          tenant,
          taskId,
          taskSchemaId,
          instructions,
          tools,
          setInstructions,
          abortController.signal
        );

        setInstructions(data);
      } catch (error) {
        setIsLoading(false);
        captureException(error);
        if (!abortController.signal.aborted) {
          return;
        }
        displayErrorToaster('Failed to improve AI agent run version - Please try again');
      }

      setIsLoading(false);
    },
    [instructions, updateTaskInstructions, tenant, taskId, taskSchemaId, setInstructions]
  );

  const cancelImproveInstructions = useCallback(() => {
    if (!isLoading) {
      return;
    }

    abortControllerRef.current?.abort();
    setIsLoading(false);
    setChangelog(undefined);

    if (oldInstructions) {
      setInstructions(oldInstructions);
      setOldInstructions(undefined);
    }
  }, [oldInstructions, setInstructions, isLoading, setChangelog]);

  const generateSuggestedInstructions = useTasks((state) => state.generateSuggestedInstructions);

  const generateInstructions = useCallback(async () => {
    abortControllerRef.current?.abort();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    setIsLoading(true);

    try {
      const data = await generateSuggestedInstructions(
        tenant,
        taskId,
        taskSchemaId,
        setInstructions,
        abortController.signal
      );
      setInstructions(data);
    } catch (error) {
      setIsLoading(false);
      captureException(error);
      if (!abortController.signal.aborted) {
        displayErrorToaster('Failed to improve AI agent run version - Please try again');
      }
      throw new Error('Failed to update AI Agent instructions');
    }

    setIsLoading(false);
  }, [generateSuggestedInstructions, setInstructions, taskId, taskSchemaId, tenant]);

  return {
    isLoading,
    oldInstructions,
    resetOldInstructions,
    improveInstructions,
    onToolsChange,
    cancelImproveInstructions,
    generateInstructions,
  };
}
