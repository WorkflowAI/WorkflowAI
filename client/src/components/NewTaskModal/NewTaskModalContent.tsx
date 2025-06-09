import { cx } from 'class-variance-authority';
import { Loader } from '@/components/ui/Loader';
import { SchemaEditorField } from '@/lib/schemaEditorUtils';
import { TenantID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { JsonSchema } from '@/types/json_schema';
import { EditSchemaModalContent } from './EditSchemaModalContent';
import { NewTaskFlowChoice } from './Import/NewTaskFlowChoice';
import { NewTaskSuggestedFeatures } from './NewTaskSuggestedFeatures';
import { ProxyEditSchemaModalContent } from './ProxyEditSchemaModalContent';
import { TaskConversation } from './TaskConversation';
import { ConversationMessage } from './TaskConversationMessage';

type NewTaskModalContentProps = {
  tenant: TenantID;
  taskSchemaId: TaskSchemaID;
  isInitialized: boolean;
  isEditMode: boolean;
  inputSplattedSchema: SchemaEditorField | undefined;
  setInputSplattedSchema: ((splattedSchema: SchemaEditorField | undefined) => void) | undefined;
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
  flow: string | undefined;
  integrationId: string | undefined;
  featureWasSelected: (
    title: string,
    inputSchema: Record<string, unknown>,
    outputSchema: Record<string, unknown>,
    message: string | undefined
  ) => void;
  onClose: () => void;
  isProxy: boolean;
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
    showRetry,
    retry,
    featureWasSelected,
    flow,
    onClose,
    isProxy,
    userFirstName,
    integrationId,
  } = props;

  if (!isInitialized) {
    return <Loader centered />;
  }

  if (!isEditMode && (!messages || messages.length === 0) && !inputSplattedSchema && !outputSplattedSchema) {
    if (flow === 'create') {
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
      <div className={cx('flex flex-col h-full w-full overflow-hidden', !open && 'invisible')}>
        <NewTaskFlowChoice onClose={onClose} tenant={tenant} />
      </div>
    );
  }

  if (!isEditMode && !inputSplattedSchema && !outputSplattedSchema) {
    return (
      <div className={cx('flex flex-col h-full w-full overflow-hidden', !open && 'invisible')}>
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
    );
  }

  if (isProxy) {
    return (
      <ProxyEditSchemaModalContent
        tenant={tenant}
        taskSchemaId={taskSchemaId}
        outputSplattedSchema={outputSplattedSchema}
        setOutputSplattedSchema={setOutputSplattedSchema}
        loading={loading}
        userMessage={userMessage}
        messages={messages}
        setUserMessage={setUserMessage}
        onSendIteration={onSendIteration}
        computedOutputSchema={computedOutputSchema}
        computedInputSchema={computedInputSchema}
        noChangesDetected={noChangesDetected}
        showRetry={showRetry}
        retry={retry}
        integrationId={integrationId}
        userFirstName={userFirstName}
      />
    );
  }

  return (
    <EditSchemaModalContent
      tenant={tenant}
      taskSchemaId={taskSchemaId}
      inputSplattedSchema={inputSplattedSchema}
      setInputSplattedSchema={setInputSplattedSchema}
      outputSplattedSchema={outputSplattedSchema}
      setOutputSplattedSchema={setOutputSplattedSchema}
      loading={loading}
      userMessage={userMessage}
      messages={messages}
      setUserMessage={setUserMessage}
      onSendIteration={onSendIteration}
      computedInputSchema={computedInputSchema}
      computedOutputSchema={computedOutputSchema}
      noChangesDetected={noChangesDetected}
      showRetry={showRetry}
      retry={retry}
      integrationId={integrationId}
      userFirstName={userFirstName}
    />
  );
}
