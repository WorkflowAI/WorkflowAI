'use client';

/* eslint-disable max-lines */
import { Link16Regular } from '@fluentui/react-icons';
import { captureException } from '@sentry/nextjs';
import { cloneDeep, set } from 'lodash';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useHotkeys } from 'react-hotkeys-hook';
import useMeasure from 'react-use-measure';
import { toast } from 'sonner';
import { useMap, useToggle } from 'usehooks-ts';
import { useNewTaskModal } from '@/components/NewTaskModal/NewTaskModal';
import TaskRunModal from '@/components/TaskRunModal/TaskRunModal';
import { Button } from '@/components/ui/Button';
import { PageContainer } from '@/components/v2/PageContainer';
import { RequestError } from '@/lib/api/client';
import { TASK_RUN_ID_PARAM } from '@/lib/constants';
import { useCopyCurrentUrl } from '@/lib/hooks/useCopy';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useIsAllowed } from '@/lib/hooks/useIsAllowed';
import { useIsMobile } from '@/lib/hooks/useIsMobile';
import { useParsedSearchParams, useRedirectWithParams } from '@/lib/queryString';
import { requiresFileSupport } from '@/lib/schemaFileUtils';
import { InitInputFromSchemaMode, initInputFromSchema } from '@/lib/schemaUtils';
import { mergeTaskInputAndVoid } from '@/lib/schemaVoidUtils';
import { scrollTo } from '@/lib/scrollUtils';
import {
  TaskRunsState,
  latestTaskRunInputSearchParams,
  useAIModels,
  useOrFetchOrganizationSettings,
  useOrFetchRunV1,
  useOrFetchVersion,
  useOrFetchVersions,
  useScheduledMetaAgentMessages,
  useTaskRuns,
  useTasks,
} from '@/store';
import { useAudioTranscriptions } from '@/store/audio_transcriptions';
import { useOrganizationSettings } from '@/store/organization_settings';
import { ToolCallName, usePlaygroundChatStore } from '@/store/playgroundChatStore';
import { useTaskPreview } from '@/store/task_preview';
import { useUpload } from '@/store/upload';
import { buildScopeKey } from '@/store/utils';
import { useVersions } from '@/store/versions';
import { StreamedChunk, TaskSchemaResponseWithSchema } from '@/types';
import { GeneralizedTaskInput } from '@/types';
import { ModelOptional, TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { StreamError, captureIfNeeded } from '@/types/errors';
import {
  MajorVersion,
  ModelResponse,
  PlaygroundState,
  RunRequest,
  RunResponseStreamChunk,
  RunV1,
  SelectedModels,
  SerializableTask,
  TaskGroupProperties_Input,
  TaskInputDict,
  VersionV1,
} from '@/types/workflowAI';
import { PlaygroundChat } from './components/Chat/PlaygroundChat';
import { RunAgentsButton } from './components/RunAgentsButton';
import { useFetchTaskRunUntilCreated } from './hooks/useFetchTaskRunUntilCreated';
import { useImproveInstructions } from './hooks/useImproveInstructions';
import { useInputGenerator } from './hooks/useInputGenerator';
import { useMatchVersion } from './hooks/useMatchVersion';
import { usePlaygroundEffects } from './hooks/usePlaygroundEffects';
import { usePlaygroundInputHistory } from './hooks/usePlaygroundInputHistory';
import { usePlaygroundParametersHistory } from './hooks/usePlaygroundParametersHistory';
import { RunTaskOptions } from './hooks/usePlaygroundPersistedState';
import { usePlaygroundPersistedState } from './hooks/usePlaygroundPersistedState';
import { useSequentialTaskRunIdUpdates } from './hooks/useSequentialTaskRunIdUpdates';
import { useTaskRunners } from './hooks/useTaskRunners';
import { usePlaygroundVariants } from './hooks/useVariants';
import { useVersionsForTaskRunners } from './hooks/useVersionsForRuns';
import { pickFinalRunProperties } from './hooks/utils';
import { PlaygroundInputContainer } from './playgroundInputContainer';
import { PlaygroundInputSettingsModal } from './playgroundInputSettingsModal';
import { PlaygroundOutput } from './playgroundOutput';
import { getReasoningEffortAndBudget } from './utils';

export type PlaygroundContentProps = {
  taskId: TaskID;
  tenant: TenantID | undefined;
  taskSchemaId: TaskSchemaID;
  userRunTasks?: () => void;
};

type PlaygroundContentBodyProps = PlaygroundContentProps & {
  aiModels: ModelResponse[];
  allAIModels: ModelResponse[];
  latestRun: RunV1 | undefined;
  versions: VersionV1[];
  taskSchema: TaskSchemaResponseWithSchema;
  task: SerializableTask;
  isTaskInitialized: boolean;
};

function getLatestTaskRunFromStoreNotReactive(
  tenant: TenantID | undefined,
  taskId: TaskID,
  taskSchemaId: number | undefined
) {
  if (taskSchemaId === undefined) {
    return undefined;
  }
  const runs = useTaskRuns.getState().taskRunsByScope.get(
    buildScopeKey({
      tenant,
      taskId,
      taskSchemaId: `${taskSchemaId}` as TaskSchemaID,
      searchParams: latestTaskRunInputSearchParams(),
    })
  );
  if (runs === undefined || runs.length === 0) {
    return undefined;
  }
  return runs[0];
}

function triggerFetchOfLatestTaskRunOfPreviousTaskSchema(
  tenant: TenantID | undefined,
  taskId: TaskID,
  taskSchemaId: TaskSchemaID,
  fetchTaskRuns: TaskRunsState['fetchTaskRuns']
) {
  if (tenant && taskId && taskSchemaId) {
    // So if the task schema is not 1, i-e there is a previous task schema,
    // we fetch the latest task run of the previous task schema to get its input
    // And use it in the input generator
    // We trigger the fetch before the instruction generation starts
    // This way we hope that the run is ready when the instructions are generated
    const taskSchemaIdNumber = Number(taskSchemaId);
    if (taskSchemaIdNumber > 1) {
      const previousTaskSchemaIdNumber = taskSchemaIdNumber - 1;
      fetchTaskRuns({
        tenant,
        taskId,
        taskSchemaId: `${taskSchemaIdNumber - 1}` as TaskSchemaID,
        searchParams: latestTaskRunInputSearchParams(),
      });
      return previousTaskSchemaIdNumber;
    }
  }
  return undefined;
}

export function PlaygroundContent(props: PlaygroundContentBodyProps) {
  const {
    aiModels,
    allAIModels,
    latestRun,
    versions,
    taskId,
    taskSchema: currentTaskSchema,
    taskSchemaId,
    tenant,
    userRunTasks,
    task,
    isTaskInitialized,
  } = props;

  const [scheduledPlaygroundStateMessage, setScheduledPlaygroundStateMessage] = useState<string | undefined>(undefined);

  const redirectWithParams = useRedirectWithParams();
  const {
    [TASK_RUN_ID_PARAM]: taskRunId,
    taskRunId1,
    taskRunId2,
    taskRunId3,
    versionId,
    showDiffMode: showDiffModeParam,
    hiddenModelColumns: hiddenModelColumnsParam,
    inputTaskRunId,
    preselectedVariantId,
    runAgents,
  } = useParsedSearchParams(
    TASK_RUN_ID_PARAM,
    'taskRunId1',
    'taskRunId2',
    'taskRunId3',
    'versionId',
    'showDiffMode',
    'hiddenModelColumns',
    'inputTaskRunId',
    'preselectedVariantId',
    'runAgents'
  );

  const playgroundOutputRef = useRef<HTMLDivElement>(null);
  const fetchTaskRunUntilCreated = useFetchTaskRunUntilCreated();
  const [streamedChunks, setStreamedChunks] = useState<(StreamedChunk | undefined)[]>(() => []);

  const {
    schemaModels,
    taskModels,
    setSchemaModels,
    modelsReasoning,
    setModelsReasoning,
    generatedInput: persistedGeneratedInput,
    showDiffMode,
    hiddenModelColumns,
    setShowDiffMode,
    setHiddenModelColumns,
    preGeneratedInput,
    setGeneratedInput: setPersistedGeneratedInput,
    setPreGeneratedInput,
    persistedTaskRunIds,
    setTaskRunId: setPersistedTaskRunId,
    persistedVersionId,
    setPersistedVersionId,
  } = usePlaygroundPersistedState({
    tenant,
    taskId,
    taskSchemaId,
    showDiffModeParam,
    hiddenModelColumnsParam,
  });

  const latestInputRef = useRef<GeneralizedTaskInput | undefined>(persistedGeneratedInput);
  latestInputRef.current = persistedGeneratedInput;

  const { version: currentVersion } = useOrFetchVersion(tenant, taskId, versionId ?? persistedVersionId);

  const isInputGenerationSupported = useMemo(() => {
    return !requiresFileSupport(
      currentTaskSchema.input_schema.json_schema,
      currentTaskSchema.input_schema.json_schema.$defs
    );
  }, [currentTaskSchema]);

  const allVersions = useMemo(() => {
    if (!currentVersion) {
      return versions;
    }
    return [...versions, currentVersion];
  }, [versions, currentVersion]);

  const { variantId, setVariantId, inputSchema, outputSchema } = usePlaygroundVariants({
    tenant,
    taskId,
    versions: allVersions,
    taskSchema: currentTaskSchema,
  });

  useEffect(() => {
    if (preselectedVariantId) {
      setVariantId(preselectedVariantId);
      redirectWithParams({
        params: { preselectedVariantId: undefined },
        scroll: false,
      });
    }
  }, [preselectedVariantId, setVariantId, redirectWithParams]);

  const {
    input: generatedInput,
    setInput: setGeneratedInput,
    isPreviousAvailable: isPreviousAvailableForInput,
    isNextAvailable: isNextAvailableForInput,
    saveToHistory: saveToHistoryForInput,
    moveToPrevious: moveToPreviousForInput,
    moveToNext: moveToNextForInput,
  } = usePlaygroundInputHistory(
    tenant,
    taskId,
    taskSchemaId,
    persistedGeneratedInput,
    setPersistedGeneratedInput,
    isInputGenerationSupported
  );

  const {
    run: inputTaskRun,
    isInitialized: inputTaskRunInitialized,
    isLoading: inputTaskRunLoading,
  } = useOrFetchRunV1(tenant, taskId, inputTaskRunId);

  const [taskIndexesLoading, setTaskIndexLoading] = useState<boolean[]>([false, false, false]);

  const { majorVersions } = useOrFetchVersions(tenant, taskId, taskSchemaId);

  const runTask = useTasks((state) => state.runTask);
  const handleTaskIndexLoadingChange = useCallback(
    (index: number, loading: boolean) =>
      setTaskIndexLoading((prev) => {
        const newTaskIndexesLoading = [...prev];
        newTaskIndexesLoading[index] = loading;
        return newTaskIndexesLoading;
      }),
    []
  );
  const handleStreamedChunk = useCallback((index: number, message: RunResponseStreamChunk | undefined) => {
    setStreamedChunks((prev) => {
      const chunks = [...prev];
      if (message) {
        chunks[index] = {
          output: message?.task_output,
          toolCalls: message?.tool_calls ?? undefined,
          reasoningSteps: message?.reasoning_steps ?? undefined,
        };
      } else {
        chunks[index] = undefined;
      }
      return chunks;
    });
  }, []);

  const {
    instructions,
    temperature,
    setInstructions,
    setTemperature,
    isPreviousAvailable: isPreviousAvailableForParameters,
    isNextAvailable: isNextAvailableForParameters,
    saveToHistory: saveToHistoryForParameters,
    moveToPrevious: moveToPreviousForParameters,
    moveToNext: moveToNextForParameters,
  } = usePlaygroundParametersHistory(tenant, taskId, taskSchemaId);

  const [userSelectedMajor, setUserSelectedMajor] = useState<number | undefined>(undefined);

  const { matchedVersion: matchedMajorVersion } = useMatchVersion({
    majorVersions,
    temperature,
    instructions,
    proxyMessages: undefined,
    variantId,
    userSelectedMajor,
    skipCheckingProxyMessages: true,
  });

  const fetchModels = useAIModels((state) => state.fetchSchemaModels);

  const [errorForModels, { set: setModelError, remove: removeModelError }] = useMap<string, Error>(
    new Map<string, Error>()
  );

  const { onTaskRunIdUpdate, onResetTaskRunIds } = useSequentialTaskRunIdUpdates({
    taskRunId1,
    taskRunId2,
    taskRunId3,
    setPersistedTaskRunId,
  });

  const createVersion = useVersions((state) => state.createVersion);

  const { noCreditsLeft } = useOrFetchOrganizationSettings();

  const fetchOrganizationSettings = useOrganizationSettings((state) => state.fetchOrganizationSettings);

  const abortControllerRun0 = useRef<AbortController | null>(null);
  const abortControllerRun1 = useRef<AbortController | null>(null);
  const abortControllerRun2 = useRef<AbortController | null>(null);

  const findAbortController = useCallback((index: number) => {
    switch (index) {
      case 0:
        return abortControllerRun0;
      case 1:
        return abortControllerRun1;
      case 2:
        return abortControllerRun2;
      default:
        return null;
    }
  }, []);

  const setAbortController = useCallback((index: number, abortController: AbortController) => {
    switch (index) {
      case 0:
        abortControllerRun0.current = abortController;
        break;
      case 1:
        abortControllerRun1.current = abortController;
        break;
      case 2:
        abortControllerRun2.current = abortController;
        break;
    }
  }, []);

  const handleRunTask = useCallback(
    async (index: number, runOptions: RunTaskOptions = {}) =>
      new Promise<void>(async (resolve, reject) => {
        const { finalGeneratedInput, finalInstructions, finalTemperature, finalVariantId } = pickFinalRunProperties(
          runOptions,
          {
            generatedInput: latestInputRef.current,
            instructions,
            temperature,
            variantId,
          }
        );

        if (!finalGeneratedInput) {
          reject('No input to run task with');
          return;
        }

        const cleanTaskRun = (model?: string, loading?: boolean) => {
          if (model) {
            removeModelError(model);
          }
          handleTaskIndexLoadingChange(index, loading ?? false);
          handleStreamedChunk(index, undefined);
          onTaskRunIdUpdate(index, undefined);
        };

        const model = runOptions.externalModel || schemaModels[index];
        if (!model) {
          cleanTaskRun();
          resolve(undefined);
          return;
        }

        const reasoning = runOptions.externalReasoning || modelsReasoning[index];
        const { effort, budget } = getReasoningEffortAndBudget(reasoning);

        cleanTaskRun(model, true);

        const oldAbortController = findAbortController(index);
        oldAbortController?.current?.abort();

        const abortController = new AbortController();
        setAbortController(index, abortController);

        try {
          const properties: TaskGroupProperties_Input = {
            model,
            instructions: finalInstructions,
            temperature: finalTemperature,
            task_variant_id: finalVariantId,
            reasoning_effort: effort,
            reasoning_budget: budget,
          };

          // We need to find or create the version that corresponds to these properties
          let id: string | undefined;
          try {
            const response = await createVersion(tenant, taskId, taskSchemaId, {
              properties,
            });
            id = response.id;
          } catch (exception: unknown) {
            cleanTaskRun(model);

            if (abortController.signal.aborted) {
              reject(undefined);
              return;
            }

            if (exception instanceof Error) {
              setModelError(model, exception);
            }

            if (exception instanceof RequestError) {
              setModelError(model, exception);
              reject(exception.rawResponse);
            } else {
              reject(exception);
            }

            return;
          }

          if (abortController.signal.aborted) {
            cleanTaskRun(model);
            reject(undefined);
            return;
          }

          if (!id) {
            cleanTaskRun(model);
            reject('Failed to create version');
            return;
          }

          setPersistedVersionId(id);

          const body: RunRequest = {
            task_input: finalGeneratedInput as Record<string, unknown>,
            version: id,
          };

          if (finalTemperature !== 0) {
            // the whole point of a higher temperature is to get more "creativity" and our cache removes that opportunity.
            body.use_cache = 'never';
          }

          const { id: run_id } = await runTask({
            tenant,
            taskId,
            taskSchemaId,
            body,
            onMessage: (message) => {
              if (abortController.signal.aborted) {
                return;
              }
              handleStreamedChunk(index, message);
            },
            signal: abortController.signal,
          });

          if (abortController.signal.aborted) {
            cleanTaskRun(model);
            reject(undefined);
            return;
          }

          await fetchTaskRunUntilCreated(tenant, taskId, run_id);
          // Running the task may have changed the models prices, so we need to refetch them
          await fetchModels(tenant, taskId, taskSchemaId);
          onTaskRunIdUpdate(index, run_id);
          resolve();
        } catch (error) {
          cleanTaskRun(model);

          if (abortController.signal.aborted) {
            reject(undefined);
            return;
          }

          if (error instanceof Error) {
            setModelError(model, error);
          }

          if (
            error instanceof StreamError &&
            !!error.extra &&
            'runId' in error.extra &&
            typeof error.extra.runId === 'string'
          ) {
            onTaskRunIdUpdate(index, error.extra.runId);
          }

          captureIfNeeded(error);
          // We don't reject here to avoid rejecting the Promise.all in handleRunTasks
          // That way if one task fails, the other ones still finish
          resolve(undefined);
        } finally {
          handleTaskIndexLoadingChange(index, false);
          fetchOrganizationSettings();
        }
      }),
    [
      instructions,
      temperature,
      variantId,
      schemaModels,
      removeModelError,
      handleTaskIndexLoadingChange,
      handleStreamedChunk,
      onTaskRunIdUpdate,
      setPersistedVersionId,
      runTask,
      tenant,
      taskId,
      taskSchemaId,
      fetchTaskRunUntilCreated,
      fetchModels,
      createVersion,
      setModelError,
      fetchOrganizationSettings,
      setAbortController,
      findAbortController,
      modelsReasoning,
    ]
  );

  const cancelRunTask = useCallback(
    (index: number) => {
      const abortController = findAbortController(index);
      abortController?.current?.abort();
    },
    [findAbortController]
  );

  const stopAllRuns = useCallback(() => {
    abortControllerRun0.current?.abort();
    abortControllerRun1.current?.abort();
    abortControllerRun2.current?.abort();
  }, []);

  useEffect(() => {
    if (!!inputTaskRun && inputTaskRunInitialized && !inputTaskRunLoading) {
      setGeneratedInput(inputTaskRun?.task_input);
      onResetTaskRunIds();
      redirectWithParams({
        params: { inputTaskRunId: undefined },
        scroll: false,
      });
    }
  }, [
    inputTaskRun,
    inputTaskRunInitialized,
    inputTaskRunLoading,
    setGeneratedInput,
    redirectWithParams,
    onResetTaskRunIds,
  ]);

  const onEdit = useCallback(
    (keyPath: string, newVal: unknown) => {
      const newGeneratedInput = cloneDeep(generatedInput) || {};
      set(newGeneratedInput, keyPath, newVal);
      setGeneratedInput(newGeneratedInput);
      onResetTaskRunIds();
    },
    [setGeneratedInput, generatedInput, onResetTaskRunIds]
  );

  const { getScheduledPlaygroundStateMessageToSendAfterRuns } = usePlaygroundChatStore();

  const handleRunTasks = useCallback(
    async (options?: RunTaskOptions, individualOptions?: Record<number, RunTaskOptions>) => {
      saveToHistoryForParameters(options?.externalInstructions);
      saveToHistoryForInput();
      onResetTaskRunIds();

      await Promise.all([
        handleRunTask(0, individualOptions?.[0] ?? options),
        handleRunTask(1, individualOptions?.[1] ?? options),
        handleRunTask(2, individualOptions?.[2] ?? options),
      ]);

      const message = getScheduledPlaygroundStateMessageToSendAfterRuns();
      if (message) {
        setScheduledPlaygroundStateMessage(message);
      }
    },
    [
      handleRunTask,
      onResetTaskRunIds,
      saveToHistoryForInput,
      saveToHistoryForParameters,
      getScheduledPlaygroundStateMessageToSendAfterRuns,
      setScheduledPlaygroundStateMessage,
    ]
  );

  // Special hack that should be not required when we finnaly remove the usePlaygroundEffects, the runAgents is set when exiting the Edit Schema Modal. Make to make the chat agent work.
  const didRequestAlreadyRunAgentsFromQueryParams = useRef(false);
  useEffect(() => {
    if (
      runAgents === 'true' &&
      !!instructions &&
      !!generatedInput &&
      !didRequestAlreadyRunAgentsFromQueryParams.current
    ) {
      didRequestAlreadyRunAgentsFromQueryParams.current = true;
      redirectWithParams({
        params: { runAgents: undefined },
        scroll: false,
      });
      handleRunTasks();
    }
  }, [runAgents, handleRunTasks, instructions, generatedInput, redirectWithParams]);

  const onUserRunTasks = useCallback(
    (options?: RunTaskOptions) => {
      userRunTasks?.();
      handleRunTasks(options);
    },
    [handleRunTasks, userRunTasks]
  );

  const setModelsAndRunTask = useCallback(
    (index: number, model: ModelOptional) => {
      setSchemaModels(index, model ?? null);
      const options = model
        ? {
            externalModel: model,
          }
        : undefined;
      saveToHistoryForParameters();
      saveToHistoryForInput();
      handleRunTask(index, options);
    },
    [handleRunTask, setSchemaModels, saveToHistoryForParameters, saveToHistoryForInput]
  );

  const setModelsReasoningAndRunTask = useCallback(
    (index: number, reasoning: string | undefined) => {
      setModelsReasoning(index, reasoning);
      const options = reasoning
        ? {
            externalReasoning: reasoning,
          }
        : undefined;
      saveToHistoryForParameters();
      saveToHistoryForInput();
      handleRunTask(index, options);
    },
    [handleRunTask, setModelsReasoning, saveToHistoryForInput, saveToHistoryForParameters]
  );

  const voidInput = useMemo(() => {
    if (!inputSchema) return undefined;
    return initInputFromSchema(inputSchema, inputSchema.$defs, InitInputFromSchemaMode.VOID);
  }, [inputSchema]);

  const resetStreamedChunks = useCallback(() => setStreamedChunks([]), []);
  const resetStreamedChunk = useCallback(
    (index: number) =>
      setStreamedChunks((prev) => {
        const newChunks = [...prev];
        newChunks[index] = undefined;
        return newChunks;
      }),
    []
  );

  const { handleGeneratePlaygroundInput, inputLoading, onStopGeneratingInput } = useInputGenerator({
    handleRunTasks,
    isInputGenerationSupported,
    preGeneratedInput,
    onResetTaskRunIds,
    saveToHistoryForInput,
    setGeneratedInput,
    setPreGeneratedInput,
    resetStreamedChunks,
    taskId,
    taskSchemaId,
    tenant,
    voidInput,
  });

  const generateSuggestedInstructions = useTasks((state) => state.generateSuggestedInstructions);

  const [areInstructionsLoading, setAreInstructionsLoading] = useState(false);
  const fetchTaskRuns = useTaskRuns((state) => state.fetchTaskRuns);

  const handleGenerateInstructions = useCallback(async () => {
    // This is triggered when a new task schema is created to migrate instructions
    // from the previous task schema

    const previousTaskSchemaIdNumber = triggerFetchOfLatestTaskRunOfPreviousTaskSchema(
      tenant,
      taskId,
      taskSchemaId,
      fetchTaskRuns
    );

    setAreInstructionsLoading(true);
    toast.promise(() => generateSuggestedInstructions(tenant, taskId, taskSchemaId, setInstructions), {
      loading: 'Generating instructions...',
      success: (data) => {
        setAreInstructionsLoading(false);
        setInstructions(data);
        // We fetch the task run from the store without reactivity to avoid
        // triggering a re-render of the component
        const latestTaskRunOfPreviousTaskSchema = getLatestTaskRunFromStoreNotReactive(
          tenant,
          taskId,
          previousTaskSchemaIdNumber
        );
        if (isInputGenerationSupported || !!latestTaskRunOfPreviousTaskSchema) {
          // TODO: pass latest input if available
          handleGeneratePlaygroundInput({
            externalInstructions: data,
            launchRuns: true,
            baseInput: latestTaskRunOfPreviousTaskSchema?.task_input,
          });
        }
        return 'Instructions generated successfully';
      },
      error: (error) => {
        captureException(error);
        setAreInstructionsLoading(false);
        return 'Failed to generate instructions';
      },
    });
  }, [
    generateSuggestedInstructions,
    tenant,
    taskId,
    taskSchemaId,
    setInstructions,
    handleGeneratePlaygroundInput,
    isInputGenerationSupported,
    fetchTaskRuns,
  ]);

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

  const onClose = useCallback(() => {
    redirectWithParams({
      params: { [TASK_RUN_ID_PARAM]: undefined },
      scroll: false,
    });
  }, [redirectWithParams]);

  const [settingsModalVisible, toggleSettingsModal] = useToggle(false);

  const onModalGenerateInput = useCallback(
    (instructions: string | undefined, temperature: number) => {
      handleGeneratePlaygroundInput({
        instructions,
        temperature,
      });
      toggleSettingsModal();
    },
    [handleGeneratePlaygroundInput, toggleSettingsModal]
  );

  const areTasksRunning = useMemo(() => {
    if (!hiddenModelColumns) {
      return taskIndexesLoading.some((l) => l);
    }
    return taskIndexesLoading.filter((_, index) => !hiddenModelColumns.includes(index)).some((l) => l);
  }, [taskIndexesLoading, hiddenModelColumns]);

  // Load the initial task run or trigger the generation of the input and runs
  const { taskRun1, taskRun2, taskRun3, taskRun1Loading, taskRun2Loading, taskRun3Loading } = usePlaygroundEffects({
    // We don't pass allAIModels here because we don't want the default model
    // to be a model that is not supported by the task schema mode.
    aiModels,
    currentVersion,
    generatedInput,
    versionId,
    handleGeneratePlaygroundInput,
    handleGenerateInstructions,
    resetStreamedChunk,
    onTaskRunIdUpdate,
    latestRun,
    schemaModels,
    taskModels,
    persistedTaskRunIds,
    setGeneratedInput,
    setInstructions,
    setSchemaModels,
    setTemperature,
    versions,
    taskId,
    taskRunId1,
    taskRunId2,
    taskRunId3,
    tenant,
    voidInput,
    persistedVersionId,
  });

  const taskRuns = useMemo(() => [taskRun1, taskRun2, taskRun3], [taskRun1, taskRun2, taskRun3]);
  const filteredTaskRunIds = useMemo(() => {
    const runs = taskRuns.filter((taskRun) => !!taskRun) as RunV1[];
    return runs.map((taskRun) => taskRun?.id ?? '');
  }, [taskRuns]);

  const playgroundOutputsLoading: [boolean, boolean, boolean] = useMemo(
    () => [
      taskIndexesLoading[0] || !!taskRun1Loading || !!streamedChunks[0],
      taskIndexesLoading[1] || !!taskRun2Loading || !!streamedChunks[1],
      taskIndexesLoading[2] || !!taskRun3Loading || !!streamedChunks[2],
    ],
    [taskIndexesLoading, taskRun1Loading, taskRun2Loading, taskRun3Loading, streamedChunks]
  );

  const onImportInput = useCallback(
    async (inputText: string) => {
      handleGeneratePlaygroundInput({
        inputText,
        successMessage: 'Input imported successfully',
      });
    },
    [handleGeneratePlaygroundInput]
  );

  const [improveVersionChangelog, setImproveVersionChangelog] = useState<string[] | undefined>(undefined);

  const handleRunTaskAndSaveInputAndParameters = useCallback(
    async (index: number) => {
      saveToHistoryForInput();
      saveToHistoryForParameters();
      await handleRunTask(index);
    },
    [handleRunTask, saveToHistoryForInput, saveToHistoryForParameters]
  );

  const taskRunners = useTaskRunners({
    playgroundOutputsLoading,
    streamedChunks,
    taskRuns,
    handleRunTask: handleRunTaskAndSaveInputAndParameters,
    cancelRunTask,
    generatedInput,
  });

  const { versionsForRuns, showSaveAllVersions, onSaveAllVersions } = useVersionsForTaskRunners({
    tenant,
    taskId,
    taskRunners,
    hiddenModelColumns,
  });

  const {
    updateTaskInstructions,
    improveInstructions,
    oldInstructions,
    resetOldInstructions,
    isImproveVersionLoading,
    cancelImproveInstructions,
  } = useImproveInstructions({
    tenant,
    taskId,
    taskSchemaId,
    instructions,
    setInstructions,
    handleRunTasks,
    setImproveVersionChangelog,
    variantId,
  });

  const fetchAudioTranscription = useAudioTranscriptions((state) => state.fetchAudioTranscription);

  const copyUrl = useCopyCurrentUrl();

  const isDisabled = inputLoading || areInstructionsLoading;

  const [containerRef, { height: containerHeight }] = useMeasure();
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const scrollToPlaygroundOutput = useCallback(() => {
    if (!playgroundOutputRef) return;
    scrollTo(scrollRef, playgroundOutputRef);
  }, [playgroundOutputRef, scrollRef]);

  const scrollToTop = useCallback(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTo({ top: 0, behavior: 'smooth' });
  }, [scrollRef]);

  const onTryPromptClick = useCallback(async () => {
    if (isDisabled) return;
    scrollToPlaygroundOutput();
    await handleRunTasks();
    scrollToPlaygroundOutput();
  }, [handleRunTasks, isDisabled, scrollToPlaygroundOutput]);

  useHotkeys('meta+enter', onTryPromptClick);

  const { openModal: openEditTaskModal } = useNewTaskModal();
  const { checkIfAllowed } = useIsAllowed();

  const { saveTaskPreview } = useTaskPreview((state) => ({
    saveTaskPreview: state.saveTaskPreview,
  }));

  const onSaveTaskPreview = useCallback(async () => {
    if (!generatedInput) return;

    const generatedInputWithVoid = mergeTaskInputAndVoid(generatedInput, voidInput);

    if (typeof generatedInputWithVoid !== 'object' || generatedInputWithVoid === null) {
      return;
    }

    const taskRun = taskRuns.find((taskRun) => !!taskRun);
    const outputFromTaskRun = taskRun?.task_output;

    await saveTaskPreview(
      `${currentTaskSchema.schema_id}` as TaskSchemaID,
      generatedInputWithVoid as Record<string, unknown>,
      outputFromTaskRun as Record<string, unknown>
    );
  }, [currentTaskSchema, generatedInput, voidInput, saveTaskPreview, taskRuns]);

  const onShowEditDescriptionModal = useCallback(async () => {
    if (!checkIfAllowed()) return;
    await onSaveTaskPreview();
    openEditTaskModal({
      mode: 'editDescription',
      redirectToPlaygrounds: 'false',
      variantId: variantId,
    });
  }, [openEditTaskModal, checkIfAllowed, onSaveTaskPreview, variantId]);

  const onShowEditSchemaModal = useCallback(
    async (message?: string) => {
      if (!checkIfAllowed()) return;
      await onSaveTaskPreview();
      openEditTaskModal({
        mode: 'editSchema',
        redirectToPlaygrounds: 'false',
        variantId: variantId,
        prefilledMessage: message,
      });
    },
    [openEditTaskModal, checkIfAllowed, onSaveTaskPreview, variantId]
  );

  const useParametersFromMajorVersion = useCallback(
    (version: MajorVersion) => {
      onResetTaskRunIds();
      if (version.properties.instructions) {
        setInstructions(version.properties.instructions);
      }
      setTemperature(version.properties.temperature);
      setVariantId(!!version.properties.task_variant_id ? version.properties.task_variant_id : undefined);
      setUserSelectedMajor(version.major);
    },
    [setInstructions, setTemperature, setUserSelectedMajor, onResetTaskRunIds, setVariantId]
  );

  const onSetInstructions = useCallback(
    (instructions: string) => {
      onResetTaskRunIds();
      setInstructions(instructions);
    },
    [setInstructions, onResetTaskRunIds]
  );

  const resetImprovedInstructions = useCallback(() => {
    setImproveVersionChangelog(undefined);
    setInstructions(oldInstructions ?? '');
    resetOldInstructions();
    onResetTaskRunIds();
  }, [setImproveVersionChangelog, resetOldInstructions, oldInstructions, setInstructions, onResetTaskRunIds]);

  const approveImprovedInstructions = useCallback(() => {
    setImproveVersionChangelog(undefined);
    resetOldInstructions();
  }, [setImproveVersionChangelog, resetOldInstructions]);

  const { isInDemoMode, onDifferentTenant } = useDemoMode();

  const playgroundState: PlaygroundState = useMemo(() => {
    const models: SelectedModels = {
      column_1: schemaModels[0] ?? null,
      column_2: schemaModels[1] ?? null,
      column_3: schemaModels[2] ?? null,
    };

    const result = {
      is_proxy: false,
      version_id: currentVersion?.id,
      version_messages: undefined,
      agent_input: generatedInput as Record<string, unknown>,
      agent_instructions: instructions,
      agent_temperature: temperature,
      agent_run_ids: filteredTaskRunIds,
      selected_models: models,
    };
    return result;
  }, [generatedInput, instructions, temperature, filteredTaskRunIds, schemaModels, currentVersion]);

  const markToolCallAsDone = usePlaygroundChatStore((state) => state.markToolCallAsDone);

  const { cancelScheduledPlaygroundMessage } = useScheduledMetaAgentMessages(
    tenant,
    taskId,
    taskSchemaId,
    playgroundState,
    scheduledPlaygroundStateMessage,
    setScheduledPlaygroundStateMessage,
    1000
  );

  const onToolCallChangeModels = useCallback(
    (
      columnsAndModels: {
        column: number;
        model: ModelOptional | undefined;
      }[]
    ) => {
      const individualOptions: Record<number, RunTaskOptions> = {};
      columnsAndModels.forEach((columnAndModel) => {
        setSchemaModels(columnAndModel.column, columnAndModel.model);
        if (columnAndModel.model) {
          individualOptions[columnAndModel.column] = {
            externalModel: columnAndModel.model,
          };
        }
      });

      saveToHistoryForParameters();
      saveToHistoryForInput();

      scrollToPlaygroundOutput();
      markToolCallAsDone(taskId, ToolCallName.RUN_CURRENT_AGENT_ON_MODELS);
      handleRunTasks(undefined, individualOptions);
    },
    [
      handleRunTasks,
      setSchemaModels,
      saveToHistoryForParameters,
      saveToHistoryForInput,
      markToolCallAsDone,
      scrollToPlaygroundOutput,
      taskId,
    ]
  );

  const onToolCallGenerateNewInput = useCallback(
    async (instructions: string | undefined) => {
      scrollToTop();
      await handleGeneratePlaygroundInput({
        launchRuns: true,
        instructions,
      });
      scrollToPlaygroundOutput();
    },
    [handleGeneratePlaygroundInput, scrollToPlaygroundOutput, scrollToTop]
  );

  const onToolCallImproveInstructions = useCallback(
    async (text: string, runId: string | undefined) => {
      scrollToTop();
      await improveInstructions(text, runId);
    },
    [improveInstructions, scrollToTop]
  );

  const onCancelChatToolCallOnPlayground = useCallback(() => {
    cancelImproveInstructions();
    onStopGeneratingInput();
    cancelScheduledPlaygroundMessage();
    stopAllRuns();
    setTimeout(() => {
      stopAllRuns();
    }, 1000);
  }, [cancelScheduledPlaygroundMessage, cancelImproveInstructions, onStopGeneratingInput, stopAllRuns]);

  const isMobile = useIsMobile();

  const shouldShowChat = useMemo(() => {
    if (isMobile) {
      return false;
    }
    if (onDifferentTenant) {
      return false;
    }
    return true;
  }, [isMobile, onDifferentTenant]);

  const addModelColumn = useCallback(() => {
    const newHiddenModelColumns = hiddenModelColumns ?? [];
    newHiddenModelColumns.pop();
    setHiddenModelColumns(newHiddenModelColumns);
  }, [hiddenModelColumns, setHiddenModelColumns]);

  const hideModelColumn = useCallback(
    (column: number) => {
      const newHiddenModelColumns = hiddenModelColumns ?? [];
      if (newHiddenModelColumns.includes(column)) {
        return;
      }
      newHiddenModelColumns.push(column);
      setHiddenModelColumns(newHiddenModelColumns);
    },
    [hiddenModelColumns, setHiddenModelColumns]
  );

  const updateInputAndRun = useCallback(
    async (input: TaskInputDict) => {
      setGeneratedInput(input);
      await new Promise((resolve) => setTimeout(resolve, 200));
      handleRunTasks();
    },
    [setGeneratedInput, handleRunTasks]
  );

  return (
    <div className='flex flex-row h-full w-full'>
      <div className='flex h-full flex-1 overflow-hidden'>
        <PageContainer
          task={task}
          isInitialized={isTaskInitialized}
          name='Playground'
          showCopyLink={false}
          showBottomBorder={true}
          documentationLink='https://docs.workflowai.com/features/playground'
          rightBarText='Your data is not used for LLM training.'
          rightBarChildren={
            <div className='flex flex-row items-center gap-2 font-lato'>
              <Button variant='newDesign' icon={<Link16Regular />} onClick={copyUrl} className='w-9 h-9 px-0 py-0' />
              {!isMobile && (
                <RunAgentsButton
                  showSaveAllVersions={showSaveAllVersions && !noCreditsLeft && !isInDemoMode}
                  areTasksRunning={areTasksRunning}
                  inputLoading={inputLoading}
                  areInstructionsLoading={areInstructionsLoading}
                  onSaveAllVersions={onSaveAllVersions}
                  onTryPromptClick={onTryPromptClick}
                  onStopAllRuns={stopAllRuns}
                />
              )}
            </div>
          }
          showBorders={!isMobile}
        >
          <div
            className='flex flex-col w-full h-full overflow-y-auto relative'
            ref={(element) => {
              containerRef(element);
              scrollRef.current = element;
            }}
            id='playground-scroll'
          >
            <div className='flex flex-col w-full sm:pb-0 pb-20'>
              <PlaygroundInputContainer
                inputSchema={inputSchema}
                generatedInput={generatedInput}
                handleGeneratePlaygroundInput={handleGeneratePlaygroundInput}
                handleRunTasks={onUserRunTasks}
                inputLoading={inputLoading}
                areInstructionsLoading={areInstructionsLoading}
                isImproveVersionLoading={isImproveVersionLoading || areInstructionsLoading}
                oldInstructions={oldInstructions}
                onEdit={onEdit}
                onImportInput={onImportInput}
                areTasksRunning={areTasksRunning}
                toggleSettingsModal={toggleSettingsModal}
                instructions={instructions}
                setInstructions={onSetInstructions}
                temperature={temperature}
                setTemperature={setTemperature}
                improveVersionChangelog={improveVersionChangelog}
                resetImprovedInstructions={resetImprovedInstructions}
                approveImprovedInstructions={approveImprovedInstructions}
                isPreviousAvailableForParameters={isPreviousAvailableForParameters}
                isNextAvailableForParameters={isNextAvailableForParameters}
                moveToPreviousForParameters={moveToPreviousForParameters}
                moveToNextForParameters={moveToNextForParameters}
                isPreviousAvailableForInput={isPreviousAvailableForInput}
                isNextAvailableForInput={isNextAvailableForInput}
                moveToPreviousForInput={moveToPreviousForInput}
                moveToNextForInput={moveToNextForInput}
                isInputGenerationSupported={isInputGenerationSupported}
                onShowEditDescriptionModal={onShowEditDescriptionModal}
                onShowEditSchemaModal={onShowEditSchemaModal}
                fetchAudioTranscription={fetchAudioTranscription}
                handleUploadFile={handleUploadFile}
                maxHeight={isMobile ? undefined : containerHeight - 50}
                matchedMajorVersion={matchedMajorVersion}
                majorVersions={majorVersions}
                useInstructionsAndTemperatureFromMajorVersion={useParametersFromMajorVersion}
                onToolsChange={updateTaskInstructions}
                onStopGeneratingInput={onStopGeneratingInput}
                isInDemoMode={isInDemoMode}
                stopAllRuns={stopAllRuns}
              />

              <div ref={playgroundOutputRef} className='flex w-full'>
                <PlaygroundOutput
                  // We pass allAIModels here because we want to display all models
                  // and disable the ones that are not supported by the task schema mode.
                  aiModels={allAIModels}
                  areInstructionsLoading={areInstructionsLoading}
                  errorForModels={errorForModels}
                  generatedInput={generatedInput}
                  improveInstructions={improveInstructions}
                  models={schemaModels}
                  onModelsChange={setModelsAndRunTask}
                  modelsReasoning={modelsReasoning}
                  onModelsReasoningChange={setModelsReasoningAndRunTask}
                  outputSchema={outputSchema}
                  showDiffMode={showDiffMode}
                  setShowDiffMode={setShowDiffMode}
                  taskId={taskId}
                  taskSchemaId={taskSchemaId}
                  taskRunners={taskRunners}
                  tenant={tenant}
                  onShowEditDescriptionModal={onShowEditDescriptionModal}
                  onShowEditSchemaModal={onShowEditSchemaModal}
                  versionsForRuns={versionsForRuns}
                  maxHeight={isMobile ? undefined : containerHeight}
                  isInDemoMode={isInDemoMode}
                  addModelColumn={addModelColumn}
                  hideModelColumn={hideModelColumn}
                  hiddenModelColumns={hiddenModelColumns}
                  isProxy={false}
                  updateInputAndRun={updateInputAndRun}
                />
              </div>
              <TaskRunModal
                tenant={tenant}
                onClose={onClose}
                open={!!taskRunId}
                taskId={taskId}
                taskRunId={taskRunId ?? ''}
                taskRunIds={!!taskRunId ? filteredTaskRunIds : []}
                taskSchemaIdFromParams={taskSchemaId}
              />
              <PlaygroundInputSettingsModal
                onModalGenerateInput={onModalGenerateInput}
                toggleModal={toggleSettingsModal}
                open={settingsModalVisible}
              />
            </div>

            <div className='fixed bottom-0 left-0 right-0 z-10 bg-white border-t border-gray-200 p-4 sm:hidden flex w-full'>
              <RunAgentsButton
                showSaveAllVersions={showSaveAllVersions && !noCreditsLeft && !isInDemoMode}
                areTasksRunning={areTasksRunning}
                inputLoading={inputLoading}
                areInstructionsLoading={areInstructionsLoading}
                onSaveAllVersions={onSaveAllVersions}
                onTryPromptClick={onTryPromptClick}
                onStopAllRuns={stopAllRuns}
                className='flex w-full'
              />
            </div>
          </div>
        </PageContainer>
      </div>
      {shouldShowChat && (
        <PlaygroundChat
          tenant={tenant}
          taskId={taskId}
          schemaId={taskSchemaId}
          playgroundState={playgroundState}
          onShowEditSchemaModal={onShowEditSchemaModal}
          improveInstructions={onToolCallImproveInstructions}
          changeModels={onToolCallChangeModels}
          generateNewInput={onToolCallGenerateNewInput}
          onCancelChatToolCallOnPlayground={onCancelChatToolCallOnPlayground}
          scrollToInput={scrollToTop}
          scrollToOutput={scrollToPlaygroundOutput}
        />
      )}
    </div>
  );
}
