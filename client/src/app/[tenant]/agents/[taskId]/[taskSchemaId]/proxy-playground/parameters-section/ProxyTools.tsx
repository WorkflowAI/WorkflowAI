import { Add16Filled } from '@fluentui/react-icons';
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { DialogContent } from '@/components/ui/Dialog';
import { Dialog } from '@/components/ui/Dialog';
import { ToolKind, Tool_Output } from '@/types/workflowAI';
import { getIcon } from '../../playground/components/Toolbox/utils';
import { getToolName } from '../../playground/components/Toolbox/utils';
import { ProxyToolDetails } from './ProxyToolDetails';

type ProxyToolsProps = {
  toolCalls: (ToolKind | Tool_Output)[] | undefined;
  setToolCalls?: (toolCalls: (ToolKind | Tool_Output)[]) => void;
  isReadonly?: boolean;
};

export function ProxyTools(props: ProxyToolsProps) {
  const { toolCalls, isReadonly = false } = props;

  const filteredTools: Tool_Output[] | undefined = useMemo(() => {
    if (!toolCalls) return undefined;

    const result: Tool_Output[] = [];
    toolCalls.forEach((tool) => {
      if ('name' in (tool as Tool_Output)) {
        result.push(tool as Tool_Output);
      }
    });

    return result.length > 0 ? result : undefined;
  }, [toolCalls]);

  const [selectedTool, setSelectedTool] = useState<Tool_Output | undefined>(undefined);

  return (
    <div className='flex flex-row gap-[10px] max-w-full min-w-[300px] items-center'>
      {filteredTools && filteredTools.length > 0 ? (
        <>
          {filteredTools.map((tool) => (
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
          {!isReadonly && (
            <Button variant='newDesign' size='none' icon={<Add16Filled />} className='w-7 h-7' disabled />
          )}
        </>
      ) : (
        <div className='flex flex-row gap-[10px] items-center'>
          <Button variant='newDesign' size='sm' icon={<Add16Filled />} disabled>
            Add Tools
          </Button>
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
    </div>
  );
}
