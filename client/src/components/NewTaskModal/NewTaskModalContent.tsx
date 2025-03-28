import { cx } from 'class-variance-authority';
import { useRef } from 'react';
import { useResizeHeight } from '@/components/NewTaskModal/useResizeHeight';
import { Loader } from '@/components/ui/Loader';
import { SchemaEditorField } from '@/lib/schemaEditorUtils';
import { TenantID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { JsonSchema } from '@/types/json_schema';
import { SchemaSplattedEditor } from '../SchemaSplattedEditor/SchemaSplattedEditor';
import { NewTaskSuggestedFeatures } from './NewTaskSuggestedFeatures';
import { TaskModalDoublePreview } from './Preview/TaskModalDoublePreview';
import { TaskConversation } from './TaskConversation';
import { ConversationMessage } from './TaskConversationMessage';

type NewTaskModalContentProps = {
  tenant: TenantID;
  taskSchemaId: TaskSchemaID;
  token: string | undefined;
  isInitialized: boolean;
  isEditMode: boolean;
  inputSplattedSchema: SchemaEditorField | undefined;
  setInputSplattedSchema: (splattedSchema: SchemaEditorField | undefined) => void;
  outputSplattedSchema: SchemaEditorField | undefined;
  setOutputSplattedSchema: (splattedSchema: SchemaEditorField | undefined) => void;
  open: boolean;
  loading: boolean;
  userMessage: string;
  userFirstName: string | undefined | null;
  messages: ConversationMessage[];
  setUserMessage: (message: string) => void;
  onSendIteration: () => Promise<void>;
  computedInputSchema: JsonSchema | undefined;
  computedOutputSchema: JsonSchema | undefined;
  noChangesDetected: boolean;
  showRetry: boolean;
  retry: () => void;
  featureWasSelected: (
    title: string,
    inputSchema: Record<string, unknown>,
    outputSchema: Record<string, unknown>,
    message: string | undefined
  ) => void;
};

export function NewTaskModalContent(props: NewTaskModalContentProps) {
  const {
    isInitialized,
    isEditMode,
    inputSplattedSchema,
    setInputSplattedSchema,
    outputSplattedSchema,
    setOutputSplattedSchema,
    open,
    loading,
    userMessage,
    messages,
    setUserMessage,
    onSendIteration,
    computedInputSchema,
    computedOutputSchema,
    noChangesDetected,
    tenant,
    taskSchemaId,
    token,
    showRetry,
    retry,
    featureWasSelected,
  } = props;

  const containerRef = useRef<HTMLDivElement>(null);
  const inputSchemaRef = useRef<HTMLDivElement>(null);
  const inputPreviewRef = useRef<HTMLDivElement>(null);

  const inputHeight = useResizeHeight({
    containerRef,
    inputSchemaRef,
    inputPreviewRef,
  });

  if (!isInitialized) {
    return <Loader centered />;
  }

  if (!isEditMode && (!messages || messages.length === 0) && !inputSplattedSchema && !outputSplattedSchema) {
    return (
      <div className={cx('flex flex-col h-full w-full overflow-hidden', !open && 'invisible')}>
        <NewTaskSuggestedFeatures
          userMessage={userMessage}
          setUserMessage={setUserMessage}
          onSendIteration={onSendIteration}
          loading={loading}
          featureWasSelected={featureWasSelected}
        />
      </div>
    );
  }

  return (
    <div className='flex flex-row w-full h-[calc(100%-60px)]' ref={containerRef}>
      <div
        className='flex flex-row w-[calc(100%-336px)] h-full overflow-y-auto overflow-x-hidden border-t border-gray-200 border-dashed'
        style={{
          opacity: `${!!inputSplattedSchema && !!outputSplattedSchema ? 100 : 0}%`,
        }}
      >
        <div className='flex flex-col w-[50%] h-max min-h-full border-r border-gray-200 border-dashed overflow-x-hidden'>
          <SchemaSplattedEditor
            title='Input Schema'
            details='This is the information you provide to the LLM'
            splattedSchema={inputSplattedSchema}
            setSplattedSchema={setInputSplattedSchema}
            style={{
              height: `${inputHeight}px`,
            }}
            contentRef={inputSchemaRef}
            className='flex w-full overflow-x-hidden'
          />
          <SchemaSplattedEditor
            title='Output Schema'
            details='This is the content you want the LLM to provide in return'
            splattedSchema={outputSplattedSchema}
            setSplattedSchema={setOutputSplattedSchema}
            disableImage
            disableAudio
            disableDocuments
            className='border-t border-gray-200 border-dashed'
          />
        </div>
        <TaskModalDoublePreview
          tenant={tenant}
          taskSchemaId={taskSchemaId}
          loading={loading}
          messages={messages}
          noChangesDetected={noChangesDetected}
          token={token}
          className='flex flex-col w-[50%] h-max min-h-full'
          computedInputSchema={computedInputSchema}
          computedOutputSchema={computedOutputSchema}
          inputPreviewRef={inputPreviewRef}
          inputHeight={inputHeight}
        />
      </div>

      <div className='w-[336px] h-full bg-white border-t border-l border-gray-200'>
        <TaskConversation
          userMessage={userMessage}
          messages={messages}
          setUserMessage={setUserMessage}
          onSendIteration={onSendIteration}
          loading={loading}
          showRetry={showRetry}
          retry={retry}
        />
      </div>
    </div>
  );
}
