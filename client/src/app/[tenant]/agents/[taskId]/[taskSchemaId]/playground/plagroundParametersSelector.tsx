'use client';

import { Loader2 } from 'lucide-react';
import { useMemo } from 'react';
import { TemperatureSelector } from '@/components/TemperatureSelector/TemperatureSelector';
import { JsonSchema } from '@/types/json_schema';
import { MajorVersion, ToolKind } from '@/types/workflowAI';
import { InstructionTextarea } from './components/Instructions/InstructionTextarea';
import { InstructionsDiffViewer } from './components/InstructionsDiffViewer';
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
  inputSchema: JsonSchema | undefined;
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
    inputSchema,
  } = props;

  const instructionsToDisplay = useMemo(() => {
    if (!isImproveVersionLoading || !oldInstructions) return instructions;
    const diff = calculateTextDiff(oldInstructions, instructions);
    return diff;
  }, [isImproveVersionLoading, oldInstructions, instructions]);

  const inputKeys = useMemo(() => {
    if (!inputSchema) return undefined;
    return Object.keys(inputSchema.properties);
  }, [inputSchema]);

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
            <InstructionTextarea text={instructionsToDisplay} onTextChange={setInstructions} inputKeys={inputKeys} />
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
