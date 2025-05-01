'use client';

import { ArrowUpload16Regular } from '@fluentui/react-icons';
import { useCallback, useMemo, useState } from 'react';
import { ObjectViewer } from '@/components';
import { Button } from '@/components/ui/Button';
import { InitInputFromSchemaMode, initInputFromSchema } from '@/lib/schemaUtils';
import { mergeTaskInputAndVoid } from '@/lib/schemaVoidUtils';
import { GeneralizedTaskInput, JsonSchema } from '@/types';
import { FileInputRequest } from '@/types/workflowAI';
import { GenerateInputControls } from './components/GenerateInputControls';
import { PlaygroundImportModal } from './playgroundImportModal';
import { TitleWithHistoryControls } from './playgroundTitleWithHistoryControls';

type PlaygroundInputProps = {
  inputSchema: JsonSchema | undefined;
  generatedInput: GeneralizedTaskInput | undefined;
  handleGeneratePlaygroundInput: () => void;
  inputLoading: boolean;
  areInstructionsLoading: boolean;
  onEdit: (keyPath: string, newVal: unknown) => void;
  onImportInput: (importedInput: string) => Promise<void>;
  areTasksRunning: boolean;
  toggleSettingsModal: () => void;
  isPreviousAvailable: boolean;
  isNextAvailable: boolean;
  moveToPrevious: () => void;
  moveToNext: () => void;
  isInputGenerationSupported: boolean;
  onShowEditDescriptionModal: () => void;
  onShowEditSchemaModal: () => void;
  fetchAudioTranscription: (payload: FileInputRequest) => Promise<string | undefined>;
  handleUploadFile: (
    formData: FormData,
    hash: string,
    onProgress?: (progress: number) => void
  ) => Promise<string | undefined>;
  onStopGeneratingInput: () => void;
  isInDemoMode: boolean;
  stopAllRuns: () => void;
};

export function PlaygroundInput(props: PlaygroundInputProps) {
  const {
    inputSchema,
    generatedInput,
    handleGeneratePlaygroundInput,
    inputLoading,
    areInstructionsLoading,
    onEdit,
    onImportInput,
    areTasksRunning,
    toggleSettingsModal,
    isPreviousAvailable,
    isNextAvailable,
    moveToPrevious,
    moveToNext,
    isInputGenerationSupported,
    onShowEditDescriptionModal,
    onShowEditSchemaModal,
    fetchAudioTranscription,
    handleUploadFile,
    onStopGeneratingInput,
    isInDemoMode,
    stopAllRuns,
  } = props;

  const [importModalOpen, setImportModalOpen] = useState(false);
  const openImportModal = useCallback(() => setImportModalOpen(true), []);
  const closeImportModal = useCallback(() => setImportModalOpen(false), []);

  const onQuickGenerateInput = useCallback(() => {
    handleGeneratePlaygroundInput();
  }, [handleGeneratePlaygroundInput]);

  const handleEdit = useCallback(
    (keyPath: string, newVal: unknown) => {
      if (areTasksRunning) {
        stopAllRuns();
      }

      if (inputLoading) {
        onStopGeneratingInput();
      }

      onEdit(keyPath, newVal);
    },
    [onEdit, areTasksRunning, inputLoading, onStopGeneratingInput, stopAllRuns]
  );

  const voidInput = useMemo(() => {
    if (!inputSchema) return undefined;
    return initInputFromSchema(inputSchema, inputSchema.$defs, InitInputFromSchemaMode.VOID);
  }, [inputSchema]);

  const generatedInputWithVoid = useMemo(() => {
    if (!generatedInput) return voidInput;
    return mergeTaskInputAndVoid(generatedInput, voidInput);
  }, [generatedInput, voidInput]);

  const onInputsClick = useCallback(() => {
    onShowEditSchemaModal();
  }, [onShowEditSchemaModal]);

  const [isHoveringOverHeader, setIsHoveringOverHeader] = useState(false);

  return (
    <div className='flex flex-col h-full w-full overflow-hidden font-lato'>
      <div
        className='flex items-center justify-between border-b border-gray-200 border-dashed h-[50px] px-4 flex-shrink-0'
        onMouseEnter={() => setIsHoveringOverHeader(true)}
        onMouseLeave={() => setIsHoveringOverHeader(false)}
      >
        <div className='flex flex-row items-center gap-3.5'>
          <TitleWithHistoryControls
            title='Input'
            isPreviousOn={isPreviousAvailable}
            isNextOn={isNextAvailable}
            tooltipPreviousText='Use previous input'
            tooltipNextText='Use next input'
            onPrevious={moveToPrevious}
            onNext={moveToNext}
            showHistoryButtons={isInputGenerationSupported}
          />

          {isHoveringOverHeader && (
            <Button
              variant='newDesign'
              onClick={onInputsClick}
              className='h-7 px-2 text-xs'
              size='none'
              disabled={isInDemoMode}
            >
              Edit Schema
            </Button>
          )}
        </div>
        {isInputGenerationSupported && (
          <div className='flex items-center'>
            <Button
              variant='newDesign'
              icon={<ArrowUpload16Regular className='h-4 w-4' />}
              onClick={openImportModal}
              disabled={areTasksRunning || areInstructionsLoading || inputLoading}
              className='h-7 w-7 mr-2 sm:block hidden'
              size='none'
            />

            <GenerateInputControls
              onQuickGenerateInput={onQuickGenerateInput}
              inputLoading={inputLoading}
              singleTaskLoading={areTasksRunning}
              areInstructionsLoading={areInstructionsLoading}
              toggleSettingsModal={toggleSettingsModal}
              onStopGeneratingInput={onStopGeneratingInput}
            />

            <PlaygroundImportModal open={importModalOpen} onClose={closeImportModal} onImport={onImportInput} />
          </div>
        )}
      </div>
      <ObjectViewer
        schema={inputSchema}
        defs={inputSchema?.$defs}
        value={generatedInputWithVoid}
        voidValue={voidInput}
        editable={true}
        onEdit={handleEdit}
        textColor='text-gray-500'
        onShowEditDescriptionModal={onShowEditDescriptionModal}
        fetchAudioTranscription={fetchAudioTranscription}
        handleUploadFile={handleUploadFile}
        className='h-max'
      />
    </div>
  );
}
