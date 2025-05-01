import { useCallback, useMemo, useState } from 'react';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { TaskSchemaResponseWithSchema } from '@/types/task';
import { VersionV1 } from '@/types/workflowAI';
import { MajorVersion } from '@/types/workflowAI';
import { usePlaygroundFirstGenerationFlow } from '../../hooks/usePlaygroundFirstGenerationFlow';
import { Tab } from '../../hooks/utils';
import { PlaygroundInput } from './Input/PlaygroundInput';
import { PlaygroundParameters } from './Parameters/PlaygroundParameters';
import { PlaygroundTabHeader } from './PlaygroundTabHeader';
import { usePlaygroundInputOutput } from './hooks/usePlaygroundInputOutput';
import { usePlaygroundParameters } from './hooks/usePlaygroundParameters';

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
};

export function PlaygroundTab(props: Props) {
  const { tenant, taskId, tab, onClose, numberOfTabs, majorVersions, onSelectMajorVersion, newestSchema } = props;
  const { majorVersion, modelId, runId } = tab;

  const [isHovering, setIsHovering] = useState(false);

  const onRun = useCallback(async () => {}, []);
  const onStopRun = useCallback(() => {}, []);

  const isRunning = false;

  const {
    schemaId,
    inputSchema,
    input,
    setInput,

    onGenerateInput,
    onStopGeneratingInput,
    isGeneratingInput,

    onMoveToPreviousInput,
    onMoveToNextInput,

    voidInput,
    isInputGenerationSupported,
  } = usePlaygroundInputOutput(tenant, taskId, tab.id, majorVersion, newestSchema);

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
    generateInstructions,
  } = usePlaygroundParameters(tenant, taskId, tab.id, majorVersion, newestSchema);

  usePlaygroundFirstGenerationFlow(
    tenant,
    taskId,
    schemaId,
    majorVersion,
    instructions,
    input,
    onGenerateInput,
    generateInstructions
  );

  const handleOnSelectMajorVersion = useCallback(
    (version: MajorVersion) => {
      onSelectMajorVersion(version);
      resetHistoryIndex();
    },
    [onSelectMajorVersion, resetHistoryIndex]
  );

  const selectedMajorVersion = useMemo(() => {
    if (!majorVersion) {
      return undefined;
    }

    if (majorVersion.properties.instructions === instructions && majorVersion.properties.temperature === temperature) {
      return majorVersion;
    }

    return undefined;
  }, [majorVersion, instructions, temperature]);

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
        <div className='flex flex-col gap-2 w-full p-4'>
          <div>Major: {majorVersion?.major}</div>
          <div>ModelId: {modelId}</div>
          <div>RunId: {runId}</div>
        </div>
      </div>
    </div>
  );
}
