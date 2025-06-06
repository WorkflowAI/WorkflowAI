import { ChevronDownFilled, ChevronUpFilled, InfoRegular } from '@fluentui/react-icons';
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { JsonSchema } from '@/types';
import { TaskID, TenantID } from '@/types/aliases';
import { ProxyMessage } from '@/types/workflowAI';
import { ProxyMessagesView } from '../proxy-messages/ProxyMessagesView';
import { getAvaibleMessageTypes } from '../proxy-messages/utils';
import { numberOfInputVariblesInInputSchema } from '../utils';
import { ProxyInputVariables } from './ProxyInputVariables';

type Props = {
  inputMessages: ProxyMessage[] | undefined;
  setInputMessages: (messages: ProxyMessage[] | undefined) => void;
  tenant: TenantID | undefined;
  taskId: TaskID;
  inputSchema: JsonSchema | undefined;
  setInputSchema: (inputSchema: JsonSchema | undefined) => void;
  input: Record<string, unknown> | undefined;
  setInput: (input: Record<string, unknown>) => void;
  onMoveToVersion: (message: ProxyMessage) => void;
  inputVariblesKeys: string[] | undefined;
};

export function ProxyInput(props: Props) {
  const {
    inputMessages,
    setInputMessages,
    inputSchema,
    setInputSchema,
    input,
    setInput,
    tenant,
    taskId,
    onMoveToVersion,
    inputVariblesKeys,
  } = props;

  const [areVariablesVisible, setAreVariablesVisible] = useState(true);

  const showInputVariables = useMemo(() => {
    return numberOfInputVariblesInInputSchema(inputSchema) > 0;
  }, [inputSchema]);

  return (
    <div className='flex flex-col w-full h-full'>
      {!!showInputVariables && (
        <div>
          <div className='flex flex-row h-[48px] w-full justify-between items-center shrink-0 border-b border-gray-200 border-dashed px-4'>
            <div className='flex flex-row items-center gap-1'>
              <div className='flex w-full items-center font-semibold text-[16px] text-gray-700'>Version Variables</div>
              <SimpleTooltip
                content={`Version variables are noted in\nversion messages with double curly\nbraces: {{variable_here}}`}
                tooltipClassName='whitespace-pre-line text-center'
                tooltipDelay={100}
              >
                <InfoRegular className='w-4 h-4 text-indigo-500' />
              </SimpleTooltip>
            </div>

            <SimpleTooltip
              content={areVariablesVisible ? 'Minimize input variables' : 'Maximize input variables'}
              tooltipClassName='whitespace-pre-line text-center'
              tooltipDelay={100}
            >
              <Button
                variant='newDesign'
                size='none'
                icon={
                  areVariablesVisible ? (
                    <ChevronUpFilled className='w-3 h-3' />
                  ) : (
                    <ChevronDownFilled className='w-3 h-3' />
                  )
                }
                className='w-5 h-5'
                onClick={() => setAreVariablesVisible(!areVariablesVisible)}
              />
            </SimpleTooltip>
          </div>
          {areVariablesVisible && (
            <ProxyInputVariables
              inputSchema={inputSchema}
              setInputSchema={setInputSchema}
              input={input as Record<string, unknown>}
              setInput={setInput}
              tenant={tenant}
              taskId={taskId}
            />
          )}
        </div>
      )}

      <div className='flex flex-row h-[48px] w-full justify-between items-center shrink-0 border-b border-gray-200 border-dashed px-4'>
        <div className='flex w-full items-center font-semibold text-[16px] text-gray-700'>Messages</div>
      </div>
      <ProxyMessagesView
        messages={inputMessages}
        setMessages={setInputMessages}
        defaultType={getAvaibleMessageTypes('input')[0]}
        avaibleTypes={getAvaibleMessageTypes('input')}
        className='px-4 py-4'
        onMoveToVersion={onMoveToVersion}
        inputVariblesKeys={inputVariblesKeys}
        supportInputVaribles={false}
      />
    </div>
  );
}
