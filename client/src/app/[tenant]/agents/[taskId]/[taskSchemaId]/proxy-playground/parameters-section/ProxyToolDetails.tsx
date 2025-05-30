import { Dismiss12Regular } from '@fluentui/react-icons';
import { useMemo } from 'react';
import { Button } from '@/components/ui/Button';
import { Tool_Output } from '@/types/workflowAI';

type ProxyToolDetailsProps = {
  tool: Tool_Output;
  close: () => void;
};

export function ProxyToolDetails(props: ProxyToolDetailsProps) {
  const { tool, close } = props;

  const inputSchemaText = useMemo(() => JSON.stringify(tool.input_schema, null, 2), [tool.input_schema]);

  return (
    <div className='flex flex-col h-full w-full'>
      <div className='flex items-center px-4 justify-between h-[52px] flex-shrink-0 border-b border-gray-200 border-dashed'>
        <div className='flex items-center gap-4 text-gray-900 text-[16px] font-semibold'>
          <Button
            onClick={close}
            variant='newDesign'
            icon={<Dismiss12Regular className='w-3 h-3' />}
            className='w-7 h-7'
            size='none'
          />
          {tool.name}
        </div>
      </div>
      <div className='flex flex-col w-full h-full p-4 gap-4'>
        <div className='text-gray-700 text-[13px]'>{tool.description}</div>
        <div className='flex flex-1 text-gray-700 text-[13px] bg-white p-3 rounded-[2px] border border-gray-200 whitespace-pre-wrap font-mono overflow-auto'>
          {inputSchemaText}
        </div>
      </div>
    </div>
  );
}
