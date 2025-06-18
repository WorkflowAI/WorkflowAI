import { useMemo } from 'react';
import { useToggle } from 'usehooks-ts';
import { useProxyInputStructure } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/hooks/useProxyInputStructure';
import { createAssistantMessageFromRun } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/proxy-messages/utils';
import {
  numberOfInputVariblesInInputSchema,
  repairMessageKeyInInput,
} from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/utils';
import { PersistantAllotment } from '@/components/PersistantAllotment';
import { useCopyRunURL } from '@/lib/hooks/useCopy';
import { useOrFetchRunCompletions } from '@/store';
import { JsonSchema, TaskSchemaResponseWithSchema } from '@/types';
import { TaskID, TenantID } from '@/types/aliases';
import { ProxyMessage, RunV1, VersionV1 } from '@/types/workflowAI';
import { PromptDialog } from '../PromptDialog';
import { TaskRunNavigation } from '../TaskRunNavigation';
import { ProxyInputVariablesView } from './ProxyInputVariablesView';
import { ProxyRunDetailsMessagesView } from './ProxyRunDetailsMessagesView';
import { ProxyRunDetailsVersionMessagesView } from './ProxyRunDetailsVersionMessagesView';
import { ProxyRunRightActions } from './ProxyRunRightActions';

type ProxyRunViewProps = {
  tenant: TenantID | undefined;
  run: RunV1;
  schema: TaskSchemaResponseWithSchema;
  onClose(): void;
  onNext: (() => void) | undefined;
  onPrev: (() => void) | undefined;
  runIndex: number;
  totalModalRuns: number;
  playgroundFullRoute: string | undefined;
  version: VersionV1;
};

export function ProxyRunView(props: ProxyRunViewProps) {
  const { onClose, onNext, onPrev, runIndex, totalModalRuns, tenant, run, schema, playgroundFullRoute, version } =
    props;
  const [promptModalVisible, togglePromptModal] = useToggle(false);

  const { completions } = useOrFetchRunCompletions(tenant, run.task_id as TaskID, run.id);
  const copyTaskRunURL = useCopyRunURL(tenant, run.task_id, run.id);

  const input = useMemo(() => {
    return repairMessageKeyInInput(run.task_input);
  }, [run.task_input]);

  const { cleanInput, messages: inputMessages } = useProxyInputStructure({
    input: input,
  });

  const inputAndOutputMessages: ProxyMessage[] | undefined = useMemo(() => {
    if (run.error) {
      return inputMessages;
    }

    const lastAssistantMessage = createAssistantMessageFromRun(run);
    return [...(inputMessages ?? []), lastAssistantMessage] as ProxyMessage[];
  }, [inputMessages, run]);

  const showInputVariables = useMemo(() => {
    return numberOfInputVariblesInInputSchema(schema.input_schema.json_schema as JsonSchema) > 0;
  }, [schema.input_schema]);

  const inputTitle = !inputAndOutputMessages || inputAndOutputMessages.length <= 1 ? 'Input' : 'Context';

  return (
    <div className='flex flex-col h-full max-h-full w-full bg-custom-gradient-1 overflow-hidden'>
      <div className='flex px-4 py-3 border-b border-dashed border-gray-200'>
        <TaskRunNavigation
          taskRunIndex={runIndex}
          totalModalRuns={totalModalRuns}
          onPrev={onPrev}
          onNext={onNext}
          onClose={onClose}
        />

        <ProxyRunRightActions
          togglePromptModal={togglePromptModal}
          playgroundFullRoute={playgroundFullRoute}
          copyTaskRunURL={copyTaskRunURL}
        />
      </div>

      <PersistantAllotment
        key={`ProxyRunView-PersistantAllotment-${showInputVariables}`}
        name={`ProxyRunView-PersistantAllotment-${showInputVariables}`}
        initialSize={showInputVariables ? [100, 100, 100] : [200, 100]}
        className='flex w-full h-full'
      >
        {showInputVariables && (
          <div className='flex flex-col h-full border-r border-dashed border-gray-200 overflow-hidden'>
            <ProxyInputVariablesView input={cleanInput} schema={schema} title={inputTitle} />
          </div>
        )}
        <div className='flex flex-col h-full border-r border-dashed border-gray-200'>
          <ProxyRunDetailsMessagesView messages={inputAndOutputMessages} error={run.error ?? undefined} />
        </div>
        <div className='flex flex-col h-full'>
          <ProxyRunDetailsVersionMessagesView version={version} run={run} tenant={tenant} />
        </div>
      </PersistantAllotment>

      {!!completions && (
        <PromptDialog open={promptModalVisible} onOpenChange={togglePromptModal} completions={completions} />
      )}
    </div>
  );
}
