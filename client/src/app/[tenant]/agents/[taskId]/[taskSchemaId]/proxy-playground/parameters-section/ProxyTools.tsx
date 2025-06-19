import { Add16Filled } from '@fluentui/react-icons';
import { useCallback, useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { DialogContent } from '@/components/ui/Dialog';
import { Dialog } from '@/components/ui/Dialog';
import { ProxyMessage, ToolKind, Tool_Output } from '@/types/workflowAI';
import { ToolboxModalContent } from '../../playground/components/Toolbox/ToolboxModalContent';
import { allTools, getIcon, getToolName } from '../../playground/components/Toolbox/utils';
import { getToolsFromMessages } from '../utils';
import { ProxyToolDetails } from './ProxyToolDetails';

type ProxyToolsProps = {
  toolCalls: (ToolKind | Tool_Output)[] | undefined;
  setToolCalls?: (toolCalls: (ToolKind | Tool_Output)[]) => void;
  isReadonly?: boolean;
  messages: ProxyMessage[] | undefined;
  onToolsChange?: (tools: ToolKind[]) => Promise<void>;
};

export function ProxyTools(props: ProxyToolsProps) {
  const { toolCalls, isReadonly = false, messages, onToolsChange } = props;

  const filteredTools: Tool_Output[] | undefined = useMemo(() => {
    if (!toolCalls) return undefined;

    const result: Tool_Output[] = [];
    toolCalls.forEach((tool) => {
      if (typeof tool === 'object' && tool && 'name' in tool) {
        result.push(tool as Tool_Output);
      }
    });

    return result.length > 0 ? result : undefined;
  }, [toolCalls]);

  const toolsFromMessages: ToolKind[] | undefined = useMemo(() => {
    return getToolsFromMessages(messages);
  }, [messages]);

  const toolsFromMessagesSet = useMemo(() => {
    return new Set(toolsFromMessages ?? []);
  }, [toolsFromMessages]);

  const onToolsUpdate = useCallback(
    async (tools: Set<ToolKind>) => {
      await onToolsChange?.(Array.from(tools).sort());
    },
    [onToolsChange]
  );

  const tools = useMemo(() => {
    return [...(filteredTools ?? []), ...(toolsFromMessages ?? [])];
  }, [filteredTools, toolsFromMessages]);

  const [selectedTool, setSelectedTool] = useState<Tool_Output | undefined>(undefined);
  const [selectedToolFromMessages, setSelectedToolFromMessages] = useState<ToolKind | undefined>(undefined);

  return (
    <div className='flex flex-row gap-[10px] max-w-full min-w-[300px] items-center'>
      {tools && tools.length > 0 ? (
        <>
          {filteredTools?.map((tool) => (
            <Button
              key={tool.name}
              variant='newDesignGray'
              size='none'
              icon={getIcon(tool.name)}
              className='px-2 py-1.5 rounded-[2px] bg-indigo-100 text-indigo-500 hover:bg-indigo-200'
              onClick={() => setSelectedTool(tool)}
            >
              {getToolName(tool.name)}
            </Button>
          ))}
          {toolsFromMessages?.map((tool) => (
            <Button
              key={tool}
              variant='newDesignGray'
              size='none'
              icon={getIcon(tool)}
              className='px-2 py-1.5 rounded-[2px] bg-indigo-100 text-indigo-500 hover:bg-indigo-200'
              onClick={() => setSelectedToolFromMessages(tool)}
            >
              {getToolName(tool)}
            </Button>
          ))}
          {!isReadonly && <Button variant='newDesign' size='none' icon={<Add16Filled />} className='w-7 h-7' />}
        </>
      ) : (
        <div className='flex flex-row gap-[10px] items-center'>
          {!isReadonly && (
            <Button
              variant='newDesign'
              size='sm'
              icon={<Add16Filled />}
              onClick={() => setSelectedToolFromMessages(allTools[0])}
            >
              Add Tools
            </Button>
          )}
          <div className='text-[13px] text-gray-500'>(Search, Web Browsing, or custom)</div>
        </div>
      )}

      {selectedTool && (
        <Dialog open={!!selectedTool} onOpenChange={() => setSelectedTool(undefined)}>
          <DialogContent className='max-w-[90vw] max-h-[90vh] w-[672px] p-0 overflow-hidden bg-custom-gradient-1 rounded-[2px] border border-gray-300'>
            <ProxyToolDetails tool={selectedTool} close={() => setSelectedTool(undefined)} />
          </DialogContent>
        </Dialog>
      )}

      {selectedToolFromMessages && (
        <Dialog open={!!selectedToolFromMessages} onOpenChange={() => setSelectedToolFromMessages(undefined)}>
          <DialogContent className='max-w-[90vw] max-h-[90vh] h-[392px] w-[672px] p-0 overflow-hidden bg-custom-gradient-1 rounded-[2px] border border-gray-300'>
            <ToolboxModalContent
              instructionsTools={toolsFromMessagesSet}
              onToolsUpdate={onToolsUpdate}
              selectedTool={selectedToolFromMessages}
              setSelectedTool={setSelectedToolFromMessages}
              close={() => setSelectedToolFromMessages(undefined)}
            />
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
