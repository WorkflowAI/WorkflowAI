import { useState } from 'react';
import { useEffect, useMemo } from 'react';
import { WORKFLOW_AI_USERNAME } from '@/lib/constants';
import { useOrFetchTaskPreview } from '@/store/fetchers';
import { TenantID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { JsonSchema } from '@/types/json_schema';
import { ChatMessage } from '@/types/workflowAI';
import { ConversationMessage } from '../TaskConversationMessage';
import { TaskModalInProgressHeader } from './TaskModalInProgressHeader';
import { TaskModalPreviewContent } from './TaskModalPreviewContent';

type Props = {
  tenant: TenantID;
  taskSchemaId: TaskSchemaID;
  loading: boolean;
  messages: ConversationMessage[];
  noChangesDetected: boolean;
  className?: string;
  computedInputSchema: JsonSchema | undefined;
  computedOutputSchema: JsonSchema | undefined;
};

export function TaskModalSinglePreview(props: Props) {
  const {
    tenant,
    taskSchemaId,
    messages,
    loading,
    noChangesDetected,
    className,
    computedInputSchema,
    computedOutputSchema,
  } = props;

  // We cannot use memos instead of states here since the we want the value to be updated after each loading but NOT be undefined while loading.

  const [chatMessages, setChatMessages] = useState<ChatMessage[] | undefined>(undefined);

  const [computedInputSchemaToUse, setComputedInputSchemaToUse] = useState<JsonSchema | undefined>(undefined);

  const [computedOutputSchemaToUse, setComputedOutputSchemaToUse] = useState<JsonSchema | undefined>(undefined);

  useEffect(() => {
    if (loading) {
      return;
    }
    setComputedInputSchemaToUse(computedInputSchema);
  }, [computedInputSchema, loading]);

  useEffect(() => {
    if (loading) {
      return;
    }
    setComputedOutputSchemaToUse(computedOutputSchema);
  }, [computedOutputSchema, loading]);

  useEffect(() => {
    if (loading) {
      return;
    }

    let chatMessages: ChatMessage[] | undefined = undefined;

    if (messages.length > 0) {
      chatMessages = messages.map((message) => ({
        role: message.username === WORKFLOW_AI_USERNAME ? 'ASSISTANT' : 'USER',
        content: message.message as string,
      }));
    }

    setChatMessages(chatMessages);
  }, [messages, loading]);

  const [previousInputPreview, setPreviousInputPreview] = useState<Record<string, unknown> | undefined>(undefined);

  const [previousOutputPreview, setPreviousOutputPreview] = useState<Record<string, unknown> | undefined>(undefined);

  const {
    generatedOutput: previewOutput,
    finalGeneratedInput: finalPreviewInput,
    finalGeneratedOutput: finalPreviewOutput,
    inputBySchemaId: previewInputBySchemaId,
    outputBySchemaId: previewOutputBySchemaId,
    isLoading: isLoadingPreviews,
  } = useOrFetchTaskPreview(
    tenant,
    taskSchemaId,
    chatMessages,
    computedInputSchemaToUse as Record<string, unknown>,
    computedOutputSchemaToUse as Record<string, unknown>,
    previousInputPreview,
    previousOutputPreview,
    loading
  );

  const shouldShowIsLoadingPreviews = useMemo(() => {
    if (noChangesDetected && !!previewInputBySchemaId && !!previewOutputBySchemaId) {
      return false;
    }
    return isLoadingPreviews;
  }, [isLoadingPreviews, noChangesDetected, previewInputBySchemaId, previewOutputBySchemaId]);

  useEffect(() => {
    if (loading) {
      return;
    }

    if (!!previewInputBySchemaId) {
      setPreviousInputPreview(previewInputBySchemaId);
    }
  }, [previewInputBySchemaId, loading]);

  useEffect(() => {
    if (loading) {
      return;
    }

    if (!!previewOutputBySchemaId) {
      setPreviousOutputPreview(previewOutputBySchemaId);
    }
  }, [previewOutputBySchemaId, loading]);

  useEffect(() => {
    if (loading) {
      return;
    }

    if (!!finalPreviewInput) {
      setPreviousInputPreview(finalPreviewInput);
    }
  }, [finalPreviewInput, loading]);

  useEffect(() => {
    if (loading) {
      return;
    }

    if (!!finalPreviewOutput) {
      setPreviousOutputPreview(finalPreviewOutput);
    }
  }, [finalPreviewOutput, loading]);

  const previewOutputToShow = useMemo(() => {
    if (noChangesDetected) {
      return previewOutputBySchemaId ?? finalPreviewOutput ?? previewOutput;
    }
    return previewOutput;
  }, [previewOutputBySchemaId, previewOutput, finalPreviewOutput, noChangesDetected]);

  return (
    <div className={className}>
      <div className='flex flex-col w-full h-full'>
        <TaskModalInProgressHeader
          title='Output (Preview)'
          inProgress={shouldShowIsLoadingPreviews && !loading}
          inProgressText='Loading Preview'
        />
        <TaskModalPreviewContent
          isLoadingPreviews={shouldShowIsLoadingPreviews}
          isLoadingNewSchema={loading}
          preview={previewOutputToShow}
          computedSchema={computedOutputSchemaToUse}
          className='flex w-full'
        />
      </div>
    </div>
  );
}
