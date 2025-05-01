import { AddFilled } from '@fluentui/react-icons';
import { useCallback, useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { DialogContent } from '@/components/ui/Dialog';
import { Dialog } from '@/components/ui/Dialog';
import { ToolKind } from '@/types/workflowAI';
import { ToolboxModalContent } from './ToolboxModalContent';
import { allTools, getIcon, getToolName } from './utils';

type PlagroundParametersToolboxProps = {
  instructions: string;
  onToolsChange: (tools: ToolKind[]) => Promise<void>;
  isLoading: boolean;
};

export function PlagroundParametersToolbox(props: PlagroundParametersToolboxProps) {
  const { instructions, onToolsChange, isLoading } = props;

  const instructionsTools = useMemo(() => {
    const result = allTools.filter((tool) => instructions.toLowerCase().includes(tool.toLowerCase()));
    return result.length > 0 ? result : undefined;
  }, [instructions]);

  const instructionsToolsSet = useMemo(() => {
    return new Set(instructionsTools ?? []);
  }, [instructionsTools]);

  const onToolsUpdate = useCallback(
    async (tools: Set<ToolKind>) => {
      await onToolsChange(Array.from(tools).sort());
    },
    [onToolsChange]
  );

  const [selectedTool, setSelectedTool] = useState<ToolKind | undefined>(undefined);

  return (
    <div className='flex flex-row gap-2 px-2 py-2 w-full rounded-b-[2px] border-l border-r border-b border-gray-300 bg-gradient-to-b from-[#F8FAFC] to-transparent items-center'>
      <Button
        variant='newDesignGray'
        size='none'
        icon={<AddFilled className='w-4 h-4' />}
        className='w-7 h-7'
        onClick={() => setSelectedTool(allTools[0])}
        disabled={isLoading}
      />
      {instructionsTools ? (
        instructionsTools.map((tool) => (
          <Button
            key={tool}
            variant='newDesignGray'
            size='none'
            icon={getIcon(tool)}
            className='px-2 py-1.5 rounded-[2px] bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
            onClick={() => setSelectedTool(tool)}
            loading={isLoading}
            disabled={isLoading}
          >
            {getToolName(tool)}
          </Button>
        ))
      ) : (
        <div className='text-[12px] text-gray-500'>Add a tool to improve your instructions</div>
      )}
      {selectedTool && (
        <Dialog open={!!selectedTool} onOpenChange={() => setSelectedTool(undefined)}>
          <DialogContent className='max-w-[90vw] max-h-[90vh] h-[392px] w-[672px] p-0 overflow-hidden bg-custom-gradient-1 rounded-[2px] border border-gray-300'>
            <ToolboxModalContent
              instructionsTools={instructionsToolsSet}
              onToolsUpdate={onToolsUpdate}
              selectedTool={selectedTool}
              setSelectedTool={setSelectedTool}
              close={() => setSelectedTool(undefined)}
            />
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
