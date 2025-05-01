import { captureException } from '@sentry/nextjs';
import { useCallback, useEffect, useRef, useState } from 'react';
import { displayErrorToaster, displaySuccessToaster } from '@/components/ui/Sonner';
import { ToolCallName, usePlaygroundChatStore } from '@/store/playgroundChatStore';
import { ImproveVersionResponse, useTasks } from '@/store/task';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { ToolKind } from '@/types/workflowAI';
import { RunTaskOptions } from './usePlaygroundPersistedState';

type ImproveInstructionsProps = {
  taskId: TaskID;
  tenant: TenantID | undefined;
  taskSchemaId: TaskSchemaID;
  instructions: string;
  variantId: string | undefined;
  setInstructions: (instructions: string) => void;
  setImproveVersionChangelog: (changelog: string[] | undefined) => void;
  handleRunTasks: (options?: RunTaskOptions) => Promise<void>;
};

export function useImproveInstructions(props: ImproveInstructionsProps) {
  const {
    tenant,
    taskId,
    taskSchemaId,
    instructions,
    variantId,
    setInstructions,
    setImproveVersionChangelog,
    handleRunTasks,
  } = props;
  const improveVersion = useTasks((state) => state.improveVersion);

  const [oldInstructions, setOldInstructions] = useState<string | undefined>(undefined);

  const resetOldInstructions = useCallback(() => {
    setOldInstructions(undefined);
  }, []);

  const instructionsRef = useRef(instructions);

  useEffect(() => {
    instructionsRef.current = instructions;
  }, [instructions]);

  const [isImproveVersionLoading, setIsImproveVersionLoading] = useState(false);
  const { markToolCallAsDone, cancelToolCall } = usePlaygroundChatStore();

  const abortControllerRef = useRef<AbortController | undefined>(undefined);

  const improveInstructions = useCallback(
    async (text: string, runId: string | undefined) => {
      abortControllerRef.current?.abort();
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      try {
        const onMessage = (message: ImproveVersionResponse) => {
          if (abortController.signal.aborted) {
            return;
          }
          const { improved_properties, changelog } = message;
          setImproveVersionChangelog(changelog);
          setIsImproveVersionLoading(true);
          const newInstructions = improved_properties.instructions || '';
          setInstructions(newInstructions);
        };

        setOldInstructions(instructionsRef.current);
        setIsImproveVersionLoading(true);

        const { improved_properties, changelog } = await improveVersion(
          tenant,
          taskId,
          {
            run_id: runId,
            user_evaluation: text,
            variant_id: variantId,
            instructions: instructionsRef.current,
          },
          onMessage,
          abortController.signal
        );

        setImproveVersionChangelog(changelog);
        const newInstructions = improved_properties.instructions || '';
        setInstructions(newInstructions);
        displaySuccessToaster('Updated Instructions generated. Rerunning AI agent...');

        setIsImproveVersionLoading(false);
        markToolCallAsDone(taskId, ToolCallName.IMPROVE_AGENT_INSTRUCTIONS);
        handleRunTasks({ externalInstructions: newInstructions });
      } catch (error) {
        cancelToolCall(ToolCallName.IMPROVE_AGENT_INSTRUCTIONS);
        setIsImproveVersionLoading(false);
        captureException(error);
        if (!abortController.signal.aborted) {
          displayErrorToaster('Failed to improve AI agent run version - Please try again');
        }
        throw new Error('Failed to improve AI agent run version');
      }
    },
    [
      improveVersion,
      taskId,
      tenant,
      setInstructions,
      handleRunTasks,
      setImproveVersionChangelog,
      variantId,
      cancelToolCall,
      markToolCallAsDone,
    ]
  );

  const updateTaskInstructions = useTasks((state) => state.updateTaskInstructions);

  const abortControllerForUpdateTaskInstructionsRef = useRef<AbortController | undefined>(undefined);

  const handleUpdateTaskInstructions = useCallback(
    async (tools: ToolKind[]) => {
      abortControllerForUpdateTaskInstructionsRef.current?.abort();
      const abortController = new AbortController();
      abortControllerForUpdateTaskInstructionsRef.current = abortController;

      setOldInstructions(instructionsRef.current);
      setIsImproveVersionLoading(true);

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
        captureException(error);
        if (!abortController.signal.aborted) {
          displayErrorToaster('Failed to improve AI agent run version - Please try again');
        }
        throw new Error('Failed to update AI Agent instructions');
      }

      setIsImproveVersionLoading(false);
    },
    [instructions, updateTaskInstructions, tenant, taskId, taskSchemaId, setInstructions]
  );

  const cancelImproveInstructions = useCallback(() => {
    if (!isImproveVersionLoading) {
      return;
    }

    abortControllerRef.current?.abort();
    setIsImproveVersionLoading(false);
    setImproveVersionChangelog(undefined);

    if (oldInstructions) {
      setInstructions(oldInstructions);
      setOldInstructions(undefined);
    }
  }, [oldInstructions, setInstructions, isImproveVersionLoading, setImproveVersionChangelog]);

  return {
    isImproveVersionLoading,
    oldInstructions,
    resetOldInstructions,
    improveInstructions,
    updateTaskInstructions: handleUpdateTaskInstructions,
    cancelImproveInstructions,
  };
}
