import { useCallback, useState } from 'react';
import { useOrFetchRunV1 } from '@/store';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { TaskSchemaResponseWithSchema } from '@/types/task';
import { VersionV1 } from '@/types/workflowAI';
import { MajorVersion } from '@/types/workflowAI';
// import { usePlaygroundFirstGenerationFlow } from '../../hooks/usePlaygroundFirstGenerationFlow';
import { Tab } from '../../hooks/utils';
import { PlaygroundInput } from './Input/PlaygroundInput';
import { PlaygroundOutput } from './Output/PlaygroundOutput';
import { PlaygroundParameters } from './Parameters/PlaygroundParameters';
import { PlaygroundTabHeader } from './PlaygroundTabHeader';
import { usePlaygroundInput } from './hooks/usePlaygroundInput';
import { usePlaygroundParameters } from './hooks/usePlaygroundParameters';
import { usePlaygroundRuns } from './hooks/usePlaygroundRuns';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  tab: Tab;
  newestSchema: TaskSchemaResponseWithSchema | undefined;
  onClose: () => void;
  numberOfTabs: number;
  versions: VersionV1[];
  majorVersions: MajorVersion[];
  onSelectMajorVersion: (version: MajorVersion) => void;
  onSelectModel: (model: string) => void;
  onSelectRun: (runId: string | undefined) => void;
};

export function PlaygroundTab(props: Props) {
  const {
    tenant,
    taskId,
    tab,
    onClose,
    numberOfTabs,
    majorVersions,
    onSelectMajorVersion,
    onSelectModel,
    onSelectRun,
    newestSchema,
  } = props;

  const { majorVersion, modelId, runId } = tab;
  const [isHovering, setIsHovering] = useState(false);

  const { run } = useOrFetchRunV1(tenant, taskId, runId);

  const {
    schemaId,
    variantId,

    inputSchema,
    outputSchema,
    input,
    setInput,

    onGenerateInput,
    onStopGeneratingInput,
    isGeneratingInput,

    onMoveToPreviousInput,
    onMoveToNextInput,

    voidInput,
    isInputGenerationSupported,
  } = usePlaygroundInput(tenant, taskId, tab.id, majorVersion, newestSchema);

  const {
    instructions,
    temperature,
    setInstructions,
    setTemperature,

    onMoveToPreviousParameters,
    onMoveToNextParameters,
    isLoading: isLoadingInstructions,

    resetHistoryIndex,

    oldInstructions,
    changelog,
    resetImprovedInstructions,
    approveImprovedInstructions,

    onToolsChange,
    // onGenerateInstructions,
    onImproveInstructions,

    selectedMajorVersion,
  } = usePlaygroundParameters(tenant, taskId, tab.id, majorVersion, schemaId, variantId);

  const {
    compatibleModels,
    onRun,
    onStopRun,
    isRunning,
    errorMessage,
    wasRunSuccessfull,
    toolCalls,
    reasoningSteps,
    output,
  } = usePlaygroundRuns(
    tenant,
    taskId,
    schemaId,
    variantId,
    runId,
    modelId,
    instructions,
    temperature,
    input,
    onSelectRun,
    run,
    majorVersion
  );

  // usePlaygroundFirstGenerationFlow(
  //   schemaId,
  //   majorVersion,
  //   instructions,
  //   input,
  //   onGenerateInput,
  //   onGenerateInstructions
  // );

  const handleOnSelectMajorVersion = useCallback(
    (version: MajorVersion) => {
      onSelectMajorVersion(version);
      resetHistoryIndex();
    },
    [onSelectMajorVersion, resetHistoryIndex]
  );

  return (
    <div
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
      className='flex h-full min-w-[500px] max-w-[500px] overflow-y-auto px-2 py-4'
    >
      <div className='flex flex-col h-max w-full border border-gray-200 rounded-[2px]'>
        <PlaygroundTabHeader showButtons={isHovering} onClose={numberOfTabs > 1 ? onClose : undefined} />
        <PlaygroundParameters
          majorVersions={majorVersions}
          selectedMajorVersion={selectedMajorVersion}
          onSelectMajorVersion={handleOnSelectMajorVersion}
          temperature={temperature}
          setTemperature={setTemperature}
          instructions={instructions}
          setInstructions={setInstructions}
          onMoveToPrevious={onMoveToPreviousParameters}
          onMoveToNext={onMoveToNextParameters}
          oldInstructions={oldInstructions}
          changelog={changelog}
          isLoading={isLoadingInstructions}
          resetImprovedInstructions={resetImprovedInstructions}
          approveImprovedInstructions={approveImprovedInstructions}
          onToolsChange={onToolsChange}
          onRun={onRun}
        />
        <PlaygroundInput
          tenant={tenant}
          taskId={taskId}
          inputSchema={inputSchema}
          input={input}
          setInput={setInput}
          voidInput={voidInput}
          onStopRun={onStopRun}
          isInputGenerationSupported={isInputGenerationSupported}
          isRunning={isRunning}
          isGeneratingInput={isGeneratingInput}
          isLoadingInstructions={isLoadingInstructions}
          onMoveToPrevious={onMoveToPreviousInput}
          onMoveToNext={onMoveToNextInput}
          onStopGeneratingInput={onStopGeneratingInput}
          onGenerateInput={onGenerateInput}
        />
        <PlaygroundOutput
          tenant={tenant}
          taskId={taskId}
          modelId={modelId}
          compatibleModels={compatibleModels}
          onSelectModel={onSelectModel}
          onRun={onRun}
          onStopRun={onStopRun}
          isRunning={isRunning}
          isGenerating={isGeneratingInput || isLoadingInstructions}
          errorMessage={errorMessage}
          wasRunSuccessfull={wasRunSuccessfull}
          outputSchema={outputSchema}
          toolCalls={toolCalls}
          reasoningSteps={reasoningSteps}
          output={output}
          run={run}
          onImproveInstructions={onImproveInstructions}
        />
      </div>
    </div>
  );
}
