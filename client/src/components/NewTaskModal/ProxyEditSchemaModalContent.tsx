import { SchemaEditorField } from '@/lib/schemaEditorUtils';
import { TenantID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { JsonSchema } from '@/types/json_schema';
import { SchemaSplattedEditor } from '../SchemaSplattedEditor/SchemaSplattedEditor';
import { TaskModalSinglePreview } from './Preview/TaskModalSinglePreview';
import { TaskConversation } from './TaskConversation';
import { ConversationMessage } from './TaskConversationMessage';

type Props = {
  tenant: TenantID;
  taskSchemaId: TaskSchemaID;
  outputSplattedSchema: SchemaEditorField | undefined;
  setOutputSplattedSchema: (splattedSchema: SchemaEditorField | undefined) => void;
  loading: boolean;
  userMessage: string;
  userFirstName: string | undefined | null;
  messages: ConversationMessage[];
  setUserMessage: (message: string) => void;
  onSendIteration: () => Promise<void>;
  computedOutputSchema: JsonSchema | undefined;
  computedInputSchema: JsonSchema | undefined;
  noChangesDetected: boolean;
  showRetry: boolean;
  retry: () => void;
  integrationId: string | undefined;
};

export function ProxyEditSchemaModalContent(props: Props) {
  const {
    outputSplattedSchema,
    setOutputSplattedSchema,
    loading,
    userMessage,
    messages,
    setUserMessage,
    onSendIteration,
    computedOutputSchema,
    computedInputSchema,
    noChangesDetected,
    tenant,
    taskSchemaId,
    showRetry,
    retry,
  } = props;

  return (
    <div className='flex flex-row w-full h-[calc(100%-60px)]'>
      <div
        className='flex flex-row w-[calc(100%-336px)] h-full overflow-y-auto overflow-x-hidden border-t border-gray-200 border-dashed'
        style={{
          opacity: `${!!outputSplattedSchema ? 100 : 0}%`,
        }}
      >
        <div className='flex flex-col w-[50%] h-max min-h-full border-r border-gray-200 border-dashed overflow-x-hidden'>
          <SchemaSplattedEditor
            title='Output Schema'
            details='This is the content you want the LLM to provide in return'
            splattedSchema={outputSplattedSchema}
            setSplattedSchema={setOutputSplattedSchema}
            disableAudio
            disableDocuments
          />
        </div>
        <TaskModalSinglePreview
          tenant={tenant}
          taskSchemaId={taskSchemaId}
          loading={loading}
          messages={messages}
          noChangesDetected={noChangesDetected}
          className='flex flex-col w-[50%] h-max min-h-full'
          computedInputSchema={computedInputSchema}
          computedOutputSchema={computedOutputSchema}
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
