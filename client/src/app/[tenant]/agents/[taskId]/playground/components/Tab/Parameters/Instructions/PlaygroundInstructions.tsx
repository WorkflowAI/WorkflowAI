import { Loader2 } from 'lucide-react';
import { useCallback } from 'react';
import { useMemo } from 'react';
import { Textarea } from '@/components/ui/Textarea';
import { ToolKind } from '@/types/workflowAI';
import { InstructionsDiffViewer } from './InstructionsDiffViewer';
import { PlagroundParametersToolbox } from './Toolbox/playgroundParametersToolbox';
import { calculateTextDiff } from './utils';

type Props = {
  instructions: string;
  setInstructions: (instructions: string) => void;
  oldInstructions: string;
  changelog: string[] | undefined;
  isLoading: boolean;
  resetImprovedInstructions: () => void;
  approveImprovedInstructions: () => void;
  onToolsChange: (tools: ToolKind[]) => Promise<void>;
};

export function PlaygroundInstructions(props: Props) {
  const {
    instructions,
    setInstructions,
    oldInstructions,
    changelog,
    isLoading,
    resetImprovedInstructions,
    approveImprovedInstructions,
    onToolsChange,
  } = props;

  const onInstructionsChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setInstructions(e.target.value);
    },
    [setInstructions]
  );

  const instructionsToDisplay = useMemo(() => {
    if (!isLoading || !oldInstructions) return instructions;
    const diff = calculateTextDiff(oldInstructions, instructions);
    return diff;
  }, [isLoading, oldInstructions, instructions]);

  return (
    <div className='flex flex-col items-top flex-1 overflow-hidden p-4'>
      <div className='flex justify-between items-center pb-1.5'>
        <div className='flex flex-row gap-2 items-center'>
          {isLoading && (
            <div className='flex items-center justify-center'>
              <Loader2 className='w-4 h-4 animate-spin text-gray-700' />
            </div>
          )}
          <div className='text-gray-900 font-medium text-[13px]'>instructions</div>
        </div>
      </div>
      {!!changelog && !!oldInstructions ? (
        <InstructionsDiffViewer
          instructions={instructions}
          oldInstructions={oldInstructions}
          improveVersionChangelog={changelog}
          resetImprovedInstructions={resetImprovedInstructions}
          approveImprovedInstructions={approveImprovedInstructions}
        />
      ) : (
        <Textarea
          className='flex text-gray-900 placeholder:text-gray-500 font-normal text-[13px] rounded-[2px] min-h-[60px] max-h-[400px] border-gray-300 overflow-y-auto focus-within:ring-inset'
          placeholder='Add any instructions regarding how you want AI agents to be run on this version...'
          value={instructionsToDisplay}
          onChange={onInstructionsChange}
        />
      )}
      <PlagroundParametersToolbox instructions={instructions} onToolsChange={onToolsChange} isLoading={isLoading} />
    </div>
  );
}
