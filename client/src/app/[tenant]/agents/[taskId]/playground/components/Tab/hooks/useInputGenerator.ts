import { useCallback, useRef } from 'react';
import { useState } from 'react';
import { toast } from 'sonner';
import { displayErrorToaster, displaySuccessToaster } from '@/components/ui/Sonner';
import { ToolCallName, usePlaygroundChatStore } from '@/store/playgroundChatStore';
import { useTasks } from '@/store/task';
import { GeneralizedTaskInput } from '@/types';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';

export type GeneratePlaygroundInputParams = {
  instructions?: string;
  temperature?: number;
  successMessage?: string;
  inputText?: string;
  baseInput?: Record<string, unknown>;
};

export function useInputGenerator(
  tenant: TenantID | undefined,
  taskId: TaskID,
  taskSchemaId: TaskSchemaID,

  setInput: (input: GeneralizedTaskInput | undefined) => void,
  voidInput: GeneralizedTaskInput | undefined
) {
  const generatePlaygroundInput = useTasks((state) => state.generatePlaygroundInput);
  const generatePlaygroundInputWithText = useTasks((state) => state.generatePlaygroundInputWithText);

  const [isGenerating, setIsGenerating] = useState(false);
  const abortController = useRef<AbortController | null>(null);

  const cancelToolCall = usePlaygroundChatStore((state) => state.cancelToolCall);
  const markToolCallAsDone = usePlaygroundChatStore((state) => state.markToolCallAsDone);

  const onGenerateInput = useCallback(
    async (params?: GeneratePlaygroundInputParams) => {
      const {
        instructions,
        temperature,
        successMessage = 'Input generated successfully',
        inputText,
        baseInput,
      } = params || {};

      abortController.current?.abort();
      const currentAbortController = new AbortController();
      abortController.current = currentAbortController;

      setInput(voidInput);
      setIsGenerating(true);

      const toastId = toast.loading('Generating input...');

      const onSuccess = (input: GeneralizedTaskInput | undefined, toastId: string | number | undefined) => {
        if (currentAbortController.signal.aborted) {
          cancelToolCall(ToolCallName.GENERATE_AGENT_INPUT);
          setIsGenerating(false);
          setInput(undefined);
          toast.dismiss(toastId);
          return;
        }

        setIsGenerating(false);
        setInput(input);

        markToolCallAsDone(taskId, ToolCallName.GENERATE_AGENT_INPUT);
        displaySuccessToaster(successMessage, undefined, toastId);
      };

      const onError = (toastId: string | number | undefined) => {
        cancelToolCall(ToolCallName.GENERATE_AGENT_INPUT);

        if (currentAbortController.signal.aborted) {
          setIsGenerating(false);
          setInput(undefined);
          toast.dismiss(toastId);
          return;
        }

        setIsGenerating(false);
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
            setInput,
            currentAbortController.signal
          );
          setInput(message);
          onSuccess(message, toastId);
          return message;
        } catch {
          onError(toastId);
          return undefined;
        }
      }

      // Input Generation
      let message: GeneralizedTaskInput;

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
          setInput,
          currentAbortController.signal
        );
        setInput(message);
        onSuccess(message, toastId);

        return message;
      } catch {
        onError(toastId);
        return undefined;
      }
    },
    [
      cancelToolCall,
      generatePlaygroundInput,
      generatePlaygroundInputWithText,
      markToolCallAsDone,
      setInput,
      taskId,
      taskSchemaId,
      tenant,
      voidInput,
    ]
  );

  const onStopGeneratingInput = useCallback(() => {
    if (abortController.current) {
      abortController.current.abort();
      abortController.current = null;
    }
  }, []);

  return {
    onGenerateInput,
    onStopGeneratingInput,
    isGenerating,
  };
}
