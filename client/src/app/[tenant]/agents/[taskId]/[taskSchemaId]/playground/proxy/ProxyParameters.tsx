import { useCallback } from 'react';
import { TemperatureSelector } from '@/components/TemperatureSelector/TemperatureSelector';
import { ToolKind, Tool_Output } from '@/types/workflowAI';
import { ProxyTextarea } from './ProxyTextarea';
import { ProxyTools } from './ProxyTools';
import { ProxyMessage, ProxyMessageContent, createEmptySystemMessage } from './utils';

type ProxyParametersProps = {
  systemMessage: ProxyMessage;
  setSystemMessage: (systemMessage: ProxyMessage) => void;
  temperature: number;
  setTemperature: (temperature: number) => void;
  handleRunTasks: () => void;
  toolCalls: (ToolKind | Tool_Output)[] | undefined;
  setToolCalls: (toolCalls: (ToolKind | Tool_Output)[] | undefined) => void;
};

export function ProxyParameters(props: ProxyParametersProps) {
  const { systemMessage, setSystemMessage, temperature, setTemperature, handleRunTasks, toolCalls, setToolCalls } =
    props;

  const onSystemMessageChange = useCallback(
    (index: number, content: ProxyMessageContent) => {
      const newSystemMessage = systemMessage ?? createEmptySystemMessage();
      const newContent = [...newSystemMessage.content];
      newContent[index] = content;
      setSystemMessage({ ...newSystemMessage, content: newContent });
    },
    [systemMessage, setSystemMessage]
  );

  return (
    <div className='flex flex-col w-full h-full'>
      <div className='flex w-full items-center px-4 h-[48px] border-b border-gray-200 border-dashed font-semibold text-[16px] text-gray-700'>
        Parameters
      </div>
      <div className='flex flex-col gap-1 px-4 pt-3'>
        <div className='flex w-full items-center font-medium text-[13px] text-gray-900'>System Message</div>
        {systemMessage?.content.map((content, index) => (
          <ProxyTextarea
            key={index}
            content={content}
            setContent={(content) => onSystemMessageChange(index, content)}
            placeholder='System message content'
            minHeight={80}
          />
        ))}
      </div>
      <div className='flex flex-col gap-1 px-4 pt-3'>
        <div className='flex w-full items-center font-medium text-[13px] text-gray-900'>Tools</div>
        <ProxyTools toolCalls={toolCalls} setToolCalls={setToolCalls} />
      </div>
      <div className='flex flex-col gap-1 px-4 pt-3 pb-4'>
        <div className='flex w-full items-center font-medium text-[13px] text-gray-900'>Temperature</div>
        <TemperatureSelector
          temperature={temperature}
          setTemperature={setTemperature}
          handleRunTasks={handleRunTasks}
        />
      </div>
    </div>
  );
}
