import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { DialogContent } from '@/components/ui/Dialog';
import { Dialog } from '@/components/ui/Dialog';
import { ToolKind, Tool_Output } from '@/types/workflowAI';
import { getIcon } from '../components/Toolbox/utils';
import { getToolName } from '../components/Toolbox/utils';
import { ProxyToolDetails } from './ProxyToolDetails';

type ProxyToolsProps = {
  toolCalls: (ToolKind | Tool_Output)[] | undefined;
  setToolCalls: (toolCalls: (ToolKind | Tool_Output)[]) => void;
};

export function ProxyTools(props: ProxyToolsProps) {
  const { toolCalls } = props;

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
    <div className='flex flex-row gap-2 px-2 py-2 max-w-full min-w-[300px] rounded-[2px] border border-gray-300 bg-gradient-to-b from-[#F8FAFC] to-transparent items-center'>
      {filteredTools ? (
        filteredTools.map((tool) => (
          <Button
            key={tool.name}
            variant='newDesignGray'
            size='none'
            icon={getIcon(tool.name)}
            className='px-2 py-1.5 rounded-[2px] bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
            onClick={() => setSelectedTool(tool)}
          >
            {getToolName(tool.name)}
          </Button>
        ))
      ) : (
        <div className='text-[12px] text-gray-500'>No tools used</div>
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
