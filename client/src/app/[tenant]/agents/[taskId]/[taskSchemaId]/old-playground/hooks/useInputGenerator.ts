import { useCallback, useEffect, useRef } from 'react';
import { useState } from 'react';
import { toast } from 'sonner';
import { displayErrorToaster, displaySuccessToaster } from '@/components/ui/Sonner';
import { ToolCallName, usePlaygroundChatStore } from '@/store/playgroundChatStore';
import { useTasks } from '@/store/task';
import { GeneralizedTaskInput } from '@/types';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { GeneratePlaygroundInputParams, RunTaskOptions } from './usePlaygroundPersistedState';

type InputGenerationIteration = {
  iteration: number;
  type: 'foreground' | 'background';
  pending: boolean;
};

type UseInputGeneratorProps = {
  handleRunTasks: (options: RunTaskOptions) => void;
  isInputGenerationSupported: boolean;
  preGeneratedInput: GeneralizedTaskInput | undefined;
  onResetTaskRunIds: () => void;
  saveToHistoryForInput: (input: GeneralizedTaskInput) => void;
  setGeneratedInput: (input: GeneralizedTaskInput | undefined) => void;
  setPreGeneratedInput: (input: GeneralizedTaskInput | undefined) => void;
  resetStreamedChunks: () => void;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  tenant: TenantID | undefined;
  voidInput: GeneralizedTaskInput | undefined;
};

export function useInputGenerator(props: UseInputGeneratorProps) {
  const {
    handleRunTasks,
    isInputGenerationSupported,
    preGeneratedInput,
    onResetTaskRunIds,
    saveToHistoryForInput,
    setGeneratedInput,
    setPreGeneratedInput,
    resetStreamedChunks,
    taskId,
    taskSchemaId,
    tenant,
    voidInput,
  } = props;
  const generatePlaygroundInput = useTasks((state) => state.generatePlaygroundInput);
  const generatePlaygroundInputWithText = useTasks((state) => state.generatePlaygroundInputWithText);
  const [inputLoading, setInputLoading] = useState(false);
  const abortController = useRef<AbortController | null>(null);

  // We want to avoid generating 2 inputs at the same time
  // because the simultaneous inputs might be identical.
  const currentIteration = useRef<InputGenerationIteration>({
    iteration: 0,
    type: 'foreground',
    pending: false,
  });

  const generateInputInBackground = useCallback(async () => {
    if (currentIteration.current?.pending || !isInputGenerationSupported) {
      return;
    }
    const iteration = currentIteration.current.iteration + 1;
    currentIteration.current = {
      iteration,
      type: 'background',
      pending: true,
    };
    const input = await generatePlaygroundInput(tenant, taskId, taskSchemaId, {});
    if (currentIteration.current.type !== 'background' || currentIteration.current.iteration !== iteration) {
      return;
    }
    setPreGeneratedInput(input);
    currentIteration.current = {
      iteration,
      type: 'background',
      pending: false,
    };
  }, [isInputGenerationSupported, generatePlaygroundInput, setPreGeneratedInput, taskId, taskSchemaId, tenant]);

  useEffect(() => {
    if (!preGeneratedInput && isInputGenerationSupported) {
      generateInputInBackground();
    }
  }, [preGeneratedInput, generateInputInBackground, isInputGenerationSupported]);

  const cancelToolCall = usePlaygroundChatStore((state) => state.cancelToolCall);
  const markToolCallAsDone = usePlaygroundChatStore((state) => state.markToolCallAsDone);

  const handleGeneratePlaygroundInput = useCallback(
    async (params?: GeneratePlaygroundInputParams) => {
      const {
        externalVersion,
        externalInstructions,
        launchRuns = false,
        instructions,
        temperature,
        successMessage = 'Input generated successfully',
        inputText,
        baseInput,
      } = params || {};

      setGeneratedInput(voidInput);
      setInputLoading(true);
      resetStreamedChunks();
      onResetTaskRunIds();

      const currentAbortController = new AbortController();
      abortController.current = currentAbortController;

      const toastId = toast.loading('Generating input...');

      const onSuccess = (input: GeneralizedTaskInput | undefined, toastId: string | number | undefined) => {
        if (currentAbortController.signal.aborted) {
          cancelToolCall(ToolCallName.GENERATE_AGENT_INPUT);
          setInputLoading(false);
          setGeneratedInput(undefined);
          toast.dismiss(toastId);
          return;
        }

        setInputLoading(false);
        setGeneratedInput(input);

        if (input) {
          saveToHistoryForInput(input);
        }

        markToolCallAsDone(taskId, ToolCallName.GENERATE_AGENT_INPUT);

        if (launchRuns === true) {
          handleRunTasks({
            externalGeneratedInput: input,
            externalVersion,
            externalInstructions,
          });
        }

        displaySuccessToaster(successMessage, undefined, toastId);
      };

      const onError = (toastId: string | number | undefined) => {
        cancelToolCall(ToolCallName.GENERATE_AGENT_INPUT);

        if (currentAbortController.signal.aborted) {
          setInputLoading(false);
          setGeneratedInput(undefined);
          toast.dismiss(toastId);
          return;
        }

        setInputLoading(false);
        displayErrorToaster('Failed to generate input', undefined, toastId);
      };

      // Input Generation with Text
      if (inputText) {
        const request = {
          inputs_text: inputText,
          base_input: baseInput,
        };

        try {
          const message = await generatePlaygroundInputWithText(
            tenant,
            taskId,
            taskSchemaId,
            request,
            setGeneratedInput,
            currentAbortController.signal
          );
          onSuccess(message, toastId);
          return;
        } catch {
          onError(toastId);
          return;
        }
      }

      // Input Generation with Pre-Generated Input
      if (instructions === undefined && temperature === undefined && !!preGeneratedInput) {
        setPreGeneratedInput(undefined);
        onSuccess(preGeneratedInput, toastId);
        return;
      }

      // Input Generation
      let message: GeneralizedTaskInput;

      const shouldGenerateInBackground =
        currentIteration.current.type === 'background' && currentIteration.current.pending;

      currentIteration.current = {
        iteration: shouldGenerateInBackground
          ? currentIteration.current.iteration
          : currentIteration.current.iteration + 1,
        type: 'foreground',
        pending: true,
      };

      const request = {
        instructions,
        group: {
          properties: {
            temperature,
          },
        },
        base_input: baseInput,
      };

      try {
        message = await generatePlaygroundInput(
          tenant,
          taskId,
          taskSchemaId,
          request,
          setGeneratedInput,
          currentAbortController.signal
        );
      } catch {
        onError(toastId);
        return;
      } finally {
        currentIteration.current = {
          iteration: currentIteration.current.iteration,
          type: 'foreground',
          pending: false,
        };
      }

      if (shouldGenerateInBackground) {
        generateInputInBackground();
      }

      onSuccess(message, toastId);
    },
    [
      setGeneratedInput,
      voidInput,
      resetStreamedChunks,
      onResetTaskRunIds,
      preGeneratedInput,
      generatePlaygroundInputWithText,
      tenant,
      taskId,
      taskSchemaId,
      setPreGeneratedInput,
      generatePlaygroundInput,
      generateInputInBackground,
      saveToHistoryForInput,
      handleRunTasks,
      cancelToolCall,
      markToolCallAsDone,
    ]
  );

  const onStopGeneratingInput = useCallback(() => {
    if (abortController.current) {
      abortController.current.abort();
      abortController.current = null;
    }
  }, []);

  return {
    handleGeneratePlaygroundInput,
    inputLoading,
    onStopGeneratingInput,
  };
}
