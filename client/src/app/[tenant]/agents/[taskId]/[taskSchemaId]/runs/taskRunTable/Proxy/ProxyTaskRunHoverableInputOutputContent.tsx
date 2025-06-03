import { useMemo } from 'react';
import { ProxyInputVariablesView } from '@/components/TaskRunModal/proxy/ProxyInputVariablesView';
import { ProxyRunDetailsMessagesView } from '@/components/TaskRunModal/proxy/ProxyRunDetailsMessagesView';
import { JsonSchema } from '@/types/json_schema';
import { TaskSchemaResponseWithSchema } from '@/types/task';
import { ProxyMessage, RunV1 } from '@/types/workflowAI';
import { useProxyInputStructure } from '../../../proxy-playground/hooks/useProxyInputStructure';
import { createAssistantMessageFromRun } from '../../../proxy-playground/proxy-messages/utils';
import { numberOfInputVariblesInInputSchema } from '../../../proxy-playground/utils';
import { repairMessageKeyInInput } from '../../../proxy-playground/utils';

type Props = {
  run: RunV1;
  schema: TaskSchemaResponseWithSchema;
};

export function ProxyTaskRunHoverableInputOutputContent(props: Props) {
  const { run, schema } = props;

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

  return (
    <div className='flex flex-row w-[50vw] max-w-[50vw] h-[50vh] text-gray-700 border border-gray-200 rounded-[2px] overflow-hidden'>
      {showInputVariables && (
        <div className='flex flex-1 h-full border-r border-gray-200 border-dashed'>
          <div className='flex h-full w-full overflow-hidden'>
            <ProxyInputVariablesView input={cleanInput} schema={schema} />
          </div>
        </div>
      )}
      <div className='flex flex-1 h-full overflow-hidden'>
        <ProxyRunDetailsMessagesView messages={inputAndOutputMessages} error={run.error ?? undefined} />
      </div>
    </div>
  );
}
