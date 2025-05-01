import Image from 'next/image';
import { useMemo } from 'react';
import { useCallback } from 'react';
import { ToolKind } from '@/types/workflowAI';
import { ToolboxMenuHeader } from './ToolboxMenuHeader';
import { ToolboxTab } from './ToolboxTab';
import { getSpecificIconURL, getSpecificToolName } from './utils';

type IndicatorProps = {
  isOn: boolean;
};

function Indicator(props: IndicatorProps) {
  const { isOn } = props;

  if (isOn) {
    return (
      <div className='w-3 h-3 flex items-center justify-center border border-indigo-500 rounded-full'>
        <div className='w-1.5 h-1.5 bg-indigo-500 rounded-full' />
      </div>
    );
  }

  return <div className='w-3 h-3 flex items-center justify-center border border-gray-400 rounded-full' />;
}

type ToolboxSearchMenuProps = {
  tab: ToolboxTab;
  tools: Set<ToolKind>;
  setTools: React.Dispatch<React.SetStateAction<Set<ToolKind>>>;
};

export function ToolboxSearchMenu(props: ToolboxSearchMenuProps) {
  const { tab, tools, setTools } = props;

  const isOn = useMemo(() => {
    return tab.tools.some((tool) => tools.has(tool));
  }, [tab, tools]);

  const toggle = useCallback(() => {
    if (isOn) {
      // Remove from tools all the tools that are in tab.tools
      setTools((prev) => {
        const newTools = new Set(prev);
        tab.tools.forEach((tool) => newTools.delete(tool));
        return newTools;
      });
    } else {
      // Add to tools first tool that are in tab.tools
      setTools((prev) => {
        const newTools = new Set(prev);
        newTools.add(tab.tools[0]);
        return newTools;
      });
    }
  }, [isOn, setTools, tab.tools]);

  const selectTool = useCallback(
    (tool: ToolKind) => {
      setTools((prev) => {
        const newTools = new Set(prev);
        tab.tools.forEach((tool) => newTools.delete(tool));
        newTools.add(tool);
        return newTools;
      });
    },
    [setTools, tab.tools]
  );

  return (
    <div className='flex flex-col gap-1'>
      <ToolboxMenuHeader
        name='Search'
        text='Get real-time answers, expert insights, and concise summaries from the web.'
        isOn={isOn}
        onSelect={toggle}
      />
      {isOn && (
        <div className='flex flex-col gap-1 px-4'>
          <div className='text-[13px] font-medium text-gray-900'>Search Engine</div>
          <div className='flex flex-col w-full'>
            {tab.tools.map((tool) => {
              const iconUrl = getSpecificIconURL(tool);
              return (
                <div
                  key={tool}
                  className='flex flex-row gap-2 border-b border-gray-200/60 last:border-b-0 py-2 cursor-pointer items-center'
                  onClick={() => selectTool(tool)}
                >
                  <Indicator isOn={tools.has(tool)} />
                  {iconUrl && <Image src={iconUrl} alt={tool} width={16} height={16} className='w-4 h-4' />}
                  <div className='text-[13px] font-medium text-gray-900'>{getSpecificToolName(tool)}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
