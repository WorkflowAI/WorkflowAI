import { GeneralizedTaskInput, JsonSchema } from '@/types';
import { FileInputRequest, MajorVersion, ToolKind } from '@/types/workflowAI';
import { RunTaskOptions } from './hooks/usePlaygroundPersistedState';
import { PlagroundParametersSelector } from './plagroundParametersSelector';
import { PlaygroundInput } from './playgroundInput';

type PlaygroundInputContainerProps = {
  maxHeight: number | undefined;
  inputSchema: JsonSchema | undefined;
  generatedInput: GeneralizedTaskInput | undefined;
  handleGeneratePlaygroundInput: () => Promise<void>;
  handleRunTasks: (options?: RunTaskOptions) => void;
  improveVersionChangelog: string[] | undefined;
  inputLoading: boolean;
  areInstructionsLoading: boolean;
  isImproveVersionLoading: boolean;
  oldInstructions: string | undefined;
  instructions: string;
  onEdit: (keyPath: string, newVal: unknown) => void;
  onImportInput: (importedInput: string) => Promise<void>;
  resetImprovedInstructions: () => void;
  approveImprovedInstructions: () => void;
  setInstructions: (value: string) => void;
  setTemperature: (value: number) => void;
  areTasksRunning: boolean;
  temperature: number;
  toggleSettingsModal: () => void;
  isPreviousAvailableForParameters: boolean;
  isNextAvailableForParameters: boolean;
  moveToPreviousForParameters: () => void;
  moveToNextForParameters: () => void;
  isPreviousAvailableForInput: boolean;
  isNextAvailableForInput: boolean;
  moveToPreviousForInput: () => void;
  moveToNextForInput: () => void;
  isInputGenerationSupported: boolean;
  onShowEditDescriptionModal: () => void;
  onShowEditSchemaModal: () => void;
  fetchAudioTranscription: (payload: FileInputRequest) => Promise<string | undefined>;
  handleUploadFile: (
    formData: FormData,
    hash: string,
    onProgress?: (progress: number) => void
  ) => Promise<string | undefined>;
  matchedMajorVersion: MajorVersion | undefined;
  majorVersions: MajorVersion[];
  useInstructionsAndTemperatureFromMajorVersion: (version: MajorVersion) => void;
  onToolsChange: (tools: ToolKind[]) => Promise<void>;
  onStopGeneratingInput: () => void;
  isInDemoMode: boolean;
  stopAllRuns: () => void;
};

export function PlaygroundInputContainer(props: PlaygroundInputContainerProps) {
  const {
    maxHeight,
    inputSchema,
    generatedInput,
    handleGeneratePlaygroundInput,
    handleRunTasks,
    improveVersionChangelog,
    inputLoading,
    areInstructionsLoading,
    isImproveVersionLoading,
    oldInstructions,
    instructions,
    onEdit,
    onImportInput,
    resetImprovedInstructions,
    approveImprovedInstructions,
    setInstructions,
    setTemperature,
    areTasksRunning,
    temperature,
    toggleSettingsModal,
    isPreviousAvailableForParameters,
    isNextAvailableForParameters,
    moveToPreviousForParameters,
    moveToNextForParameters,
    isPreviousAvailableForInput,
    isNextAvailableForInput,
    moveToPreviousForInput,
    moveToNextForInput,
    isInputGenerationSupported,
    onShowEditDescriptionModal,
    onShowEditSchemaModal,
    fetchAudioTranscription,
    handleUploadFile,
    matchedMajorVersion,
    majorVersions,
    useInstructionsAndTemperatureFromMajorVersion,
    onToolsChange,
    onStopGeneratingInput,
    isInDemoMode,
    stopAllRuns,
  } = props;

  return (
    <div className='flex flex-col sm:flex-row sm:flex-1 border-b border-gray-200 border-dashed' style={{ maxHeight }}>
      <div className='flex sm:flex-1 sm:w-1/2 border-r border-gray-200 border-dashed'>
        <PlaygroundInput
          inputSchema={inputSchema}
          generatedInput={generatedInput}
          handleGeneratePlaygroundInput={handleGeneratePlaygroundInput}
          inputLoading={inputLoading}
          areInstructionsLoading={areInstructionsLoading}
          onEdit={onEdit}
          areTasksRunning={areTasksRunning}
          toggleSettingsModal={toggleSettingsModal}
          onImportInput={onImportInput}
          isPreviousAvailable={isPreviousAvailableForInput}
          isNextAvailable={isNextAvailableForInput}
          moveToPrevious={moveToPreviousForInput}
          moveToNext={moveToNextForInput}
          isInputGenerationSupported={isInputGenerationSupported}
          onShowEditDescriptionModal={onShowEditDescriptionModal}
          onShowEditSchemaModal={onShowEditSchemaModal}
          fetchAudioTranscription={fetchAudioTranscription}
          handleUploadFile={handleUploadFile}
          onStopGeneratingInput={onStopGeneratingInput}
          isInDemoMode={isInDemoMode}
          stopAllRuns={stopAllRuns}
        />
      </div>

      <div className='flex sm:flex-1 sm:w-1/2 h-full sm:border-t-0 border-t sm:pb-0 pb-2 border-gray-200 border-dashed'>
        <PlagroundParametersSelector
          isImproveVersionLoading={isImproveVersionLoading}
          oldInstructions={oldInstructions}
          instructions={instructions}
          setInstructions={setInstructions}
          temperature={temperature}
          setTemperature={setTemperature}
          improveVersionChangelog={improveVersionChangelog}
          resetImprovedInstructions={resetImprovedInstructions}
          approveImprovedInstructions={approveImprovedInstructions}
          handleRunTasks={handleRunTasks}
          isPreviousAvailable={isPreviousAvailableForParameters}
          isNextAvailable={isNextAvailableForParameters}
          moveToPrevious={moveToPreviousForParameters}
          moveToNext={moveToNextForParameters}
          matchedMajorVersion={matchedMajorVersion}
          majorVersions={majorVersions}
          useInstructionsAndTemperatureFromMajorVersion={useInstructionsAndTemperatureFromMajorVersion}
          onToolsChange={onToolsChange}
        />
      </div>
    </div>
  );
}
