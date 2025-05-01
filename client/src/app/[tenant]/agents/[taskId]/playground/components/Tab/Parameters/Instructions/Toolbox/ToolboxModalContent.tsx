import { Dismiss12Regular } from '@fluentui/react-icons';
import { useCallback, useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { ToolKind } from '@/types/workflowAI';
import { ToolboxModalTab } from './ToolboxModalTab';
import { ToolboxModalTabContent } from './ToolboxModalTabContent';
import { ToolboxTab, tabs } from './ToolboxTab';

function isTabOn(tab: ToolboxTab, tools: Set<ToolKind>) {
  return tab.tools.some((tool) => tools.has(tool));
}

type ToolboxModalContentProps = {
  instructionsTools: Set<ToolKind>;
  onToolsUpdate: (tools: Set<ToolKind>) => Promise<void>;
  selectedTool: ToolKind;
  setSelectedTool: (tool: ToolKind) => void;
  close: () => void;
};

export function ToolboxModalContent(props: ToolboxModalContentProps) {
  const { instructionsTools, onToolsUpdate, selectedTool, setSelectedTool, close } = props;

  const [tools, setTools] = useState<Set<ToolKind>>(instructionsTools);

  const areThereChanges = useMemo(() => {
    if (tools.size !== instructionsTools.size) return true;

    for (const tool of tools) {
      if (!instructionsTools.has(tool)) return true;
    }
    for (const tool of instructionsTools) {
      if (!tools.has(tool)) return true;
    }

    return false;
  }, [instructionsTools, tools]);

  const selectedTab = useMemo(() => {
    return tabs.find((tab) => tab.tools.includes(selectedTool));
  }, [selectedTool]);

  const onSave = useCallback(async () => {
    await onToolsUpdate(tools);
    close();
  }, [onToolsUpdate, tools, close]);

  if (!selectedTab) {
    return null;
  }

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
          Tools
        </div>
        <Button onClick={() => onSave()} variant='newDesign' disabled={!areThereChanges}>
          Save
        </Button>
      </div>
      <div className='flex flex-row w-full h-full'>
        <div className='flex flex-col w-[35%] h-full border-r border-gray-100 px-2 py-3'>
          {tabs.map((tab) => (
            <ToolboxModalTab
              key={tab.name}
              tab={tab}
              isSelected={tab.name === selectedTab?.name}
              isOn={isTabOn(tab, tools)}
              onSelect={() => setSelectedTool(tab.tools[0])}
            />
          ))}
        </div>
        <div className='flex flex-col w-[65%] h-full'>
          <ToolboxModalTabContent tab={selectedTab} tools={tools} setTools={setTools} />
        </div>
      </div>
    </div>
  );
}
