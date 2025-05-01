import { useMemo } from 'react';
import { useCallback } from 'react';
import { ToolKind } from '@/types/workflowAI';
import { ToolboxMenuHeader } from './ToolboxMenuHeader';
import { ToolboxTab } from './ToolboxTab';

type ToolboxBrowserMenuProps = {
  tab: ToolboxTab;
  tools: Set<ToolKind>;
  setTools: React.Dispatch<React.SetStateAction<Set<ToolKind>>>;
};

export function ToolboxBrowserMenu(props: ToolboxBrowserMenuProps) {
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

  return (
    <div className='flex flex-col gap-4'>
      <ToolboxMenuHeader name='Browser' text='Fetch the text content of a webpage.' isOn={isOn} onSelect={toggle} />
    </div>
  );
}
