'use client';

import { Loader2 } from 'lucide-react';
import { useCallback, useMemo } from 'react';
import { TemperatureSelector } from '@/components/TemperatureSelector/TemperatureSelector';
import { Textarea } from '@/components/ui/Textarea';
import { MajorVersion, ToolKind } from '@/types/workflowAI';
import { InstructionsDiffViewer } from '../../playground/components/Tab/Parameters/InstructionsDiffViewer';
import { MajorVersionCombobox } from './components/MajorVersionSelector/MajorVersionSelector';
import { PlagroundParametersToolbox } from './components/Toolbox/playgroundParametersToolbox';
import { RunTaskOptions } from './hooks/usePlaygroundPersistedState';
import { calculateTextDiff } from './hooks/utils';
import { TitleWithHistoryControls } from './playgroundTitleWithHistoryControls';

type PlaygroundParametersSelectorProps = {
  isImproveVersionLoading: boolean;
  oldInstructions: string | undefined;
  instructions: string;
  setInstructions: (value: string) => void;
  temperature: number;
  setTemperature: (value: number) => void;
  improveVersionChangelog: string[] | undefined;
  resetImprovedInstructions: () => void;
  approveImprovedInstructions: () => void;
  handleRunTasks: (options?: RunTaskOptions) => void;
  isPreviousAvailable: boolean;
  isNextAvailable: boolean;
  moveToPrevious: () => void;
  moveToNext: () => void;
  matchedMajorVersion: MajorVersion | undefined;
  majorVersions: MajorVersion[];
  useInstructionsAndTemperatureFromMajorVersion: (version: MajorVersion) => void;
  onToolsChange: (tools: ToolKind[]) => Promise<void>;
};

export function PlagroundParametersSelector(props: PlaygroundParametersSelectorProps) {
  const {
    isImproveVersionLoading,
    oldInstructions,
    instructions,
    setInstructions,
    temperature,
    setTemperature,
    improveVersionChangelog,
    resetImprovedInstructions,
    approveImprovedInstructions,
    handleRunTasks,
    isPreviousAvailable,
    isNextAvailable,
    moveToPrevious,
    moveToNext,
    matchedMajorVersion,
    majorVersions,
    useInstructionsAndTemperatureFromMajorVersion,
    onToolsChange,
  } = props;

  const onInstructionsChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setInstructions(e.target.value);
    },
    [setInstructions]
  );

  const instructionsToDisplay = useMemo(() => {
    if (!isImproveVersionLoading || !oldInstructions) return instructions;
    const diff = calculateTextDiff(oldInstructions, instructions);
    return diff;
  }, [isImproveVersionLoading, oldInstructions, instructions]);

  return (
    <div className='flex flex-col overflow-hidden w-full h-full'>
      <div className='flex sm:flex-row flex-col sm:gap-1 gap-3 justify-between sm:items-center items-start border-b border-gray-200 border-dashed px-4 sm:h-[50px] sm:py-0 py-3 flex-shrink-0'>
        <TitleWithHistoryControls
          title='Parameters'
          isPreviousOn={isPreviousAvailable}
          isNextOn={isNextAvailable}
          tooltipPreviousText='Use previous parameters'
          tooltipNextText='Use next parameters'
          onPrevious={moveToPrevious}
          onNext={moveToNext}
          showHistoryButtons={true}
        />
        <MajorVersionCombobox
          majorVersions={majorVersions}
          matchedMajorVersion={matchedMajorVersion}
          useInstructionsAndTemperatureFromMajorVersion={useInstructionsAndTemperatureFromMajorVersion}
        />
      </div>
      <div className='flex flex-col gap-3 px-4 py-2 text-gray-900 text-[13px] font-medium h-full overflow-hidden'>
        <div className='flex flex-col items-top flex-1 overflow-hidden'>
          <div className='flex justify-between items-center pb-1.5'>
            <div className='flex flex-row gap-2 items-center'>
              {isImproveVersionLoading && (
                <div className='flex items-center justify-center'>
                  <Loader2 className='w-4 h-4 animate-spin text-gray-700' />
                </div>
              )}
              <div>Instructions</div>
            </div>
          </div>
          {!!improveVersionChangelog && !!oldInstructions ? (
            <InstructionsDiffViewer
              instructions={instructions}
              oldInstructions={oldInstructions}
              improveVersionChangelog={improveVersionChangelog}
              resetImprovedInstructions={resetImprovedInstructions}
              approveImprovedInstructions={approveImprovedInstructions}
            />
          ) : (
            <Textarea
              className='flex text-gray-900 placeholder:text-gray-500 font-normal text-[13px] rounded-[2px] min-h-[60px] border-gray-300 overflow-y-auto focus-within:ring-inset'
              placeholder='Add any instructions regarding how you want AI agents to be run on this version...'
              value={instructionsToDisplay}
              onChange={onInstructionsChange}
            />
          )}
          <PlagroundParametersToolbox
            instructions={instructions}
            onToolsChange={onToolsChange}
            isLoading={isImproveVersionLoading}
          />
        </div>
        <div className='flex flex-col gap-1'>
          <div>Temperature</div>
          <TemperatureSelector
            temperature={temperature}
            setTemperature={setTemperature}
            handleRunTasks={handleRunTasks}
          />
        </div>
      </div>
    </div>
  );
}
