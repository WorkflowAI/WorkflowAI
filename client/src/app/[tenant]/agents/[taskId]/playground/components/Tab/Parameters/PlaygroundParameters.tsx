import { TemperatureSelector } from '@/components/TemperatureSelector/TemperatureSelector';
import { ToolKind } from '@/types/workflowAI';
import { MajorVersion } from '@/types/workflowAI';
import { TitleWithHistoryControls } from '../components/TitleWithHistoryControls';
import { PlaygroundInstructions } from './Instructions/PlaygroundInstructions';
import { MajorVersionCombobox } from './MajorVersionSelector/MajorVersionCombobox';

type Props = {
  majorVersions: MajorVersion[];
  selectedMajorVersion: MajorVersion | undefined;
  onSelectMajorVersion: (version: MajorVersion) => void;

  instructions: string | undefined;
  setInstructions: (instructions: string) => void;
  temperature: number | undefined;
  setTemperature: (temperature: number) => void;

  onMoveToPrevious: (() => void) | undefined;
  onMoveToNext: (() => void) | undefined;

  oldInstructions: string | undefined;
  changelog: string[] | undefined;
  isLoading: boolean;
  resetImprovedInstructions: () => void;
  approveImprovedInstructions: () => void;
  onToolsChange: (tools: ToolKind[]) => Promise<void>;

  onRun: () => void;
};

export function PlaygroundParameters(props: Props) {
  const {
    majorVersions,
    selectedMajorVersion,
    onSelectMajorVersion,
    onMoveToPrevious,
    onMoveToNext,
    instructions,
    setInstructions,
    temperature,
    setTemperature,
    oldInstructions,
    changelog,
    isLoading,
    resetImprovedInstructions,
    approveImprovedInstructions,
    onToolsChange,
    onRun,
  } = props;

  return (
    <div className='flex flex-col w-full border-b border-gray-200'>
      <div className='flex flex-row border-b border-gray-200 w-full bg-gray-50 justify-between h-[48px] items-center px-4'>
        <TitleWithHistoryControls
          title='Parameters'
          isPreviousOn={!!onMoveToPrevious}
          isNextOn={!!onMoveToNext}
          tooltipPreviousText='Use previous parameters'
          tooltipNextText='Use next parameters'
          onPrevious={onMoveToPrevious}
          onNext={onMoveToNext}
          showHistoryButtons={true}
        />

        <MajorVersionCombobox
          majorVersions={majorVersions}
          selectedMajorVersion={selectedMajorVersion}
          onSelectMajorVersion={onSelectMajorVersion}
        />
      </div>
      <PlaygroundInstructions
        instructions={instructions ?? ''}
        setInstructions={setInstructions}
        oldInstructions={oldInstructions ?? ''}
        changelog={changelog}
        isLoading={isLoading}
        resetImprovedInstructions={resetImprovedInstructions}
        approveImprovedInstructions={approveImprovedInstructions}
        onToolsChange={onToolsChange}
      />
      <div className='flex flex-col gap-1 px-4 pb-4'>
        <div className='text-gray-900 font-medium text-[13px]'>temperature</div>
        <TemperatureSelector
          temperature={temperature ?? 0}
          setTemperature={setTemperature}
          handleRunTasks={() => onRun()}
        />
      </div>
    </div>
  );
}
