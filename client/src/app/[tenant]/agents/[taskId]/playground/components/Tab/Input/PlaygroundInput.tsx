import { ArrowUpload16Regular } from '@fluentui/react-icons';
import { cloneDeep, set } from 'lodash';
import { useCallback, useMemo, useState } from 'react';
import { TitleWithHistoryControls } from '@/app/[tenant]/agents/[taskId]/playground/components/Tab/components/TitleWithHistoryControls';
import { ObjectViewer } from '@/components/ObjectViewer/ObjectViewer';
import { Button } from '@/components/ui/Button';
import { mergeTaskInputAndVoid } from '@/lib/schemaVoidUtils';
import { useAudioTranscriptions } from '@/store/audio_transcriptions';
import { useUpload } from '@/store/upload';
import { GeneralizedTaskInput, JsonSchema } from '@/types';
import { TaskID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';
import { GeneratePlaygroundInputParams } from '../hooks/useInputGenerator';
import { GenerateInputControls } from './GenerateInputControls';
import { PlaygroundImportModal } from './PlaygroundImportModal';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  inputSchema: JsonSchema | undefined;
  input: GeneralizedTaskInput | undefined;
  setInput: (input: GeneralizedTaskInput) => void;
  voidInput: GeneralizedTaskInput | undefined;
  onMoveToPrevious: (() => void) | undefined;
  onMoveToNext: (() => void) | undefined;
  onStopRun: () => void;
  onStopGeneratingInput: () => void;
  isInputGenerationSupported: boolean;
  isRunning: boolean;
  isGeneratingInput: boolean;
  isLoadingInstructions: boolean;
  onGenerateInput: (params?: GeneratePlaygroundInputParams | undefined) => Promise<void>;
};

export function PlaygroundInput(props: Props) {
  const {
    tenant,
    taskId,
    inputSchema,
    input,
    setInput,
    voidInput,
    onMoveToPrevious,
    onMoveToNext,
    onStopRun,
    onStopGeneratingInput,
    isInputGenerationSupported,
    isRunning,
    isGeneratingInput,
    isLoadingInstructions,
    onGenerateInput,
  } = props;

  const inputWithVoid = useMemo(() => {
    if (!input) return voidInput;
    return mergeTaskInputAndVoid(input, voidInput);
  }, [input, voidInput]);

  const onEdit = useCallback(
    (keyPath: string, newVal: unknown) => {
      onStopRun();
      onStopGeneratingInput();

      const newGeneratedInput = cloneDeep(input) || {};
      set(newGeneratedInput, keyPath, newVal);
      setInput(newGeneratedInput);
    },
    [onStopRun, onStopGeneratingInput, input, setInput]
  );

  const [importModalOpen, setImportModalOpen] = useState(false);

  const onImportInput = useCallback(
    async (inputText: string) => {
      onGenerateInput({
        inputText,
        successMessage: 'Input imported successfully',
      });
    },
    [onGenerateInput]
  );

  const { getUploadURL } = useUpload();
  const handleUploadFile = useCallback(
    async (formData: FormData, hash: string, onProgress?: (progress: number) => void) => {
      if (!tenant || !taskId) return undefined;
      return getUploadURL({
        tenant,
        taskId,
        form: formData,
        hash,
        onProgress,
      });
    },
    [getUploadURL, tenant, taskId]
  );

  const fetchAudioTranscription = useAudioTranscriptions((state) => state.fetchAudioTranscription);

  return (
    <div className='flex flex-col w-full border-b border-gray-200'>
      <div className='flex flex-row border-b border-gray-200 w-full bg-gray-50 justify-between h-[48px] items-center px-4'>
        <TitleWithHistoryControls
          title='Input'
          isPreviousOn={!!onMoveToPrevious}
          isNextOn={!!onMoveToNext}
          tooltipPreviousText='Use previous parameters'
          tooltipNextText='Use next parameters'
          onPrevious={onMoveToPrevious}
          onNext={onMoveToNext}
          showHistoryButtons={true}
        />

        {isInputGenerationSupported && (
          <div className='flex items-center'>
            <Button
              variant='newDesign'
              icon={<ArrowUpload16Regular className='h-4 w-4' />}
              onClick={() => setImportModalOpen(true)}
              disabled={isRunning || isLoadingInstructions || isGeneratingInput}
              className='h-7 w-7 mr-2 sm:block hidden'
              size='none'
            />

            <GenerateInputControls
              onGenerateInput={onGenerateInput}
              isGeneratingInput={isGeneratingInput}
              isRunning={isRunning}
              isLoadingInstructions={isLoadingInstructions}
              onStopGeneratingInput={onStopGeneratingInput}
            />

            <PlaygroundImportModal
              open={importModalOpen}
              onClose={() => setImportModalOpen(false)}
              onImport={onImportInput}
            />
          </div>
        )}
      </div>
      <ObjectViewer
        schema={inputSchema}
        defs={inputSchema?.$defs}
        value={inputWithVoid}
        voidValue={voidInput}
        editable={true}
        onEdit={onEdit}
        textColor='text-gray-500'
        // onShowEditDescriptionModal={onShowEditDescriptionModal}
        fetchAudioTranscription={fetchAudioTranscription}
        handleUploadFile={handleUploadFile}
        className='max-h-[400px]'
      />
    </div>
  );
}
