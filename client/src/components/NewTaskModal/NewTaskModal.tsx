'use client';

/* eslint-disable max-lines */
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { cloneDeep } from 'lodash';
import { usePathname, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useIsMounted, useToggle } from 'usehooks-ts';
import { useVariants } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/hooks/useVariants';
import { AlertDialog } from '@/components/ui/AlertDialog';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { WORKFLOW_AI_USERNAME } from '@/lib/constants';
import { NEW_TASK_MODAL_OPEN, useQueryParamModal } from '@/lib/globalModal';
import { useIsAllowed } from '@/lib/hooks/useIsAllowed';
import { useLoggedInTenantID, useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { useParsedSearchParams, useRedirectWithParams } from '@/lib/queryString';
import { TENANT_PLACEHOLDER, replaceTaskSchemaId, taskSchemaRoute } from '@/lib/routeFormatter';
import {
  SchemaEditorField,
  areSchemasEquivalent,
  fromSchemaToSplattedEditorFields,
  fromSplattedEditorFieldsToSchema,
} from '@/lib/schemaEditorUtils';
import { mergeSchemas } from '@/lib/schemaUtils';
import { useOrFetchCurrentTaskSchema, useOrFetchToken, useOrFetchVersions, useTasks } from '@/store';
import { ToolCallName, usePlaygroundChatStore } from '@/store/playgroundChatStore';
import { useTaskSchemas } from '@/store/task_schemas';
import { JsonSchema } from '@/types';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { BuildAgentIteration, CreateAgentRequest } from '@/types/workflowAI';
import { useAuth } from '../../lib/AuthContext';
import { DescriptionExampleEditor } from '../DescriptionExampleEditor/DescriptionExampleEditor';
import { displayErrorToaster } from '../ui/Sonner';
import { NewTaskModalContent } from './NewTaskModalContent';
import { NewTaskModalHeader } from './NewTaskModalHeader';
import { ConversationMessage } from './TaskConversationMessage';

const INITIAL_ASSISTANT_MESSAGE = 'Here is your task schema';

dayjs.extend(relativeTime);

function computeSendIterationPreviousIterations(
  previousIterations: BuildAgentIteration[],
  computedInputSchema: Record<string, unknown> | undefined,
  computedOutputSchema: Record<string, unknown> | undefined
) {
  if (previousIterations.length === 0) {
    return [];
  }
  const lastIteration = cloneDeep(previousIterations[previousIterations.length - 1]);
  const processedLastIteration = {
    ...lastIteration,
    task_schema: {
      ...lastIteration.task_schema,
      task_name: lastIteration?.task_schema?.task_name || '',
      input_json_schema: computedInputSchema || {},
      output_json_schema: computedOutputSchema || {},
    },
  };
  return [...previousIterations.slice(0, -1), processedLastIteration];
}

export type NewTaskModalQueryParams = {
  mode: 'new' | 'editSchema' | 'editDescription';
  redirectToPlaygrounds: string;
  variantId?: string;
  prefilledMessage?: string;
};

const searchParams: (keyof NewTaskModalQueryParams)[] = [
  'mode',
  'redirectToPlaygrounds',
  'variantId',
  'prefilledMessage',
];

export function useNewTaskModal() {
  return useQueryParamModal<NewTaskModalQueryParams>(NEW_TASK_MODAL_OPEN, searchParams);
}

export function NewTaskModal() {
  const { tenant, taskId, taskSchemaId } = useTaskSchemaParams();
  const loggedInTenant = useLoggedInTenantID();

  const { taskSchema: currentTaskSchema, isInitialized: taskSchemaInitialized } = useOrFetchCurrentTaskSchema(
    tenant,
    taskId,
    taskSchemaId
  );

  const { open, closeModal: onClose } = useNewTaskModal();

  const {
    mode: modeValue,
    redirectToPlaygrounds: redirectToPlaygroundsValue,
    variantId,
    prefilledMessage,
  } = useParsedSearchParams('mode', 'redirectToPlaygrounds', 'variantId', 'prefilledMessage');

  const { versions } = useOrFetchVersions(tenant, taskId);

  const { inputSchema: inputSchemaForVariant, outputSchema: outputSchemaForVariant } = useVariants({
    tenant,
    taskId,
    versions: versions,
    taskSchema: currentTaskSchema,
    variantId: variantId,
  });

  const mode = modeValue as NewTaskModalQueryParams['mode'];
  const isEditMode = mode === 'editSchema' || mode === 'editDescription';

  const redirectToPlaygrounds = redirectToPlaygroundsValue === 'true';

  const iterateTaskInputOutput = useTasks((s) => s.iterateTaskInputOutput);

  const [previousIterations, setPreviousIterations] = useState<BuildAgentIteration[]>([]);

  const [streamedIteration, setStreamedIteration] = useState<BuildAgentIteration | undefined>(undefined);

  const mergedWithPreviousStreamedIteration = useMemo(() => {
    if (!streamedIteration) return undefined;
    if (previousIterations.length === 0) return streamedIteration;

    const lastIteration = previousIterations[previousIterations.length - 1];

    const oldTaskSchema = lastIteration.task_schema;
    const newTaskSchema = streamedIteration.task_schema;

    const oldInputSchema = oldTaskSchema?.input_json_schema;
    const newInputSchema = newTaskSchema?.input_json_schema;
    const mergedInputSchema = mergeSchemas(oldInputSchema, newInputSchema);

    const oldOutputSchema = oldTaskSchema?.output_json_schema;
    const newOutputSchema = newTaskSchema?.output_json_schema;
    const mergedOutputSchema = mergeSchemas(oldOutputSchema, newOutputSchema);

    const mergedIteration = {
      ...streamedIteration,
      task_schema: {
        ...newTaskSchema,
        input_json_schema: mergedInputSchema,
        output_json_schema: mergedOutputSchema,
      },
    };

    return mergedIteration;
  }, [previousIterations, streamedIteration]);

  const allIterations = useMemo(() => {
    if (!mergedWithPreviousStreamedIteration) return previousIterations;
    return [...previousIterations, mergedWithPreviousStreamedIteration];
  }, [previousIterations, mergedWithPreviousStreamedIteration]);

  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [streamingMessage, setStreamingMessage] = useState<ConversationMessage | undefined>(undefined);

  const [showRetry, setShowRetry] = useState(false);

  const allMessages = useMemo(() => {
    if (!streamingMessage) return messages;
    return [...messages, streamingMessage];
  }, [messages, streamingMessage]);

  const [userMessage, setUserMessage] = useState<string>('');
  const { user } = useAuth();
  const fullName = user?.fullName;
  const userFirstName = user?.firstName;
  const userImageUrl = user?.imageUrl;

  const { token } = useOrFetchToken();

  const redirectWithParams = useRedirectWithParams();

  const taskSchema = useMemo(() => {
    // Iterate through the previous iterations to find the last task schema
    for (let i = allIterations.length - 1; i >= 0; i--) {
      const iteration = allIterations[i];
      if (iteration.task_schema) {
        return iteration.task_schema;
      }
    }
  }, [allIterations]);
  const inputSchema = taskSchema?.input_json_schema as JsonSchema | undefined;
  const outputSchema = taskSchema?.output_json_schema as JsonSchema | undefined;
  const taskName = taskSchema?.task_name ?? currentTaskSchema?.name;

  const [inputSplattedSchema, setInputSplattedSchema] = useState<SchemaEditorField | undefined>();
  const [outputSplattedSchema, setOutputSplattedSchema] = useState<SchemaEditorField | undefined>();

  useEffect(() => {
    if (!inputSchema) return;
    const newInputSplattedSchema = fromSchemaToSplattedEditorFields(inputSchema, '', inputSchema?.$defs);
    setInputSplattedSchema(newInputSplattedSchema);
  }, [inputSchema]);

  useEffect(() => {
    if (!outputSchema) return;
    const newOutputSplattedSchema = fromSchemaToSplattedEditorFields(outputSchema, '', outputSchema?.$defs);
    setOutputSplattedSchema(newOutputSplattedSchema);
  }, [outputSchema]);

  const computedInputSchema = useMemo(() => {
    if (!inputSplattedSchema) return undefined;
    const { schema, definitions } = fromSplattedEditorFieldsToSchema(inputSplattedSchema);

    return {
      ...schema,
      $defs: definitions,
    };
  }, [inputSplattedSchema]);

  const computedOutputSchema = useMemo(() => {
    if (!outputSplattedSchema) return undefined;
    const { schema, definitions } = fromSplattedEditorFieldsToSchema(outputSplattedSchema);
    return {
      ...schema,
      $defs: definitions,
    };
  }, [outputSplattedSchema]);

  const [loading, setLoading] = useState(false);

  const noChangesDetected = useMemo(() => {
    if (!computedInputSchema || !computedOutputSchema) return true;
    if (loading) return true;
    if (!isEditMode) return false;

    const inputIsEqual = areSchemasEquivalent(computedInputSchema as JsonSchema, inputSchemaForVariant);

    const outputIsEqual = areSchemasEquivalent(computedOutputSchema as JsonSchema, outputSchemaForVariant);

    return inputIsEqual && outputIsEqual;
  }, [computedInputSchema, computedOutputSchema, inputSchemaForVariant, outputSchemaForVariant, loading, isEditMode]);

  const router = useRouter();
  const pathname = usePathname();
  const updateTaskSchema = useTasks((state) => state.updateTaskSchema);
  const createTask = useTasks((state) => state.createTask);
  const fetchTaskSchema = useTaskSchemas((state) => state.fetchTaskSchema);
  const fetchTask = useTasks((state) => state.fetchTask);

  const { cancelToolCall, markToolCallAsDone } = usePlaygroundChatStore();

  const onSave = useCallback(async () => {
    if (!computedInputSchema || !computedOutputSchema) return;

    const payload: CreateAgentRequest = {
      chat_messages: messages.map((message) => ({
        content: message.message as string,
        role: message.username === WORKFLOW_AI_USERNAME ? 'ASSISTANT' : 'USER',
      })),
      name: taskName || `AI agent ${dayjs().format('YYYY-MM-DD-HH-mm-ss')}`,
      input_schema: computedInputSchema,
      output_schema: computedOutputSchema,
    };

    if (isEditMode) {
      const task = await updateTaskSchema(loggedInTenant, taskId, payload);

      const updatedTaskSchemaId = !!task.schema_id ? (`${task.schema_id}` as TaskSchemaID) : taskSchemaId;

      markToolCallAsDone(taskId, ToolCallName.EDIT_AGENT_SCHEMA);

      if (!!loggedInTenant) {
        await fetchTaskSchema(loggedInTenant, taskId, updatedTaskSchemaId);
        // We fetch the task to update the task switcher available schemas
        await fetchTask(loggedInTenant, taskId);

        if (redirectToPlaygrounds) {
          router.push(taskSchemaRoute(loggedInTenant, taskId, `${task.schema_id}` as TaskSchemaID));
        } else {
          if (taskSchemaId === updatedTaskSchemaId) {
            redirectWithParams({
              params: {
                newTaskName: task.name,
                newTaskId: task.id,
                newTaskSchemaId: task.schema_id,
                newTenantId: loggedInTenant,
                newTaskModalOpen: undefined,
                mode: undefined,
                redirectToPlaygrounds: undefined,
                runAgents: 'true',
              },
              scroll: false,
            });
          } else {
            const newUrl = replaceTaskSchemaId(pathname, updatedTaskSchemaId) + '?runAgents=true';
            router.push(newUrl);
          }
        }

        return;
      }

      onClose();
      return;
    }

    const task = await createTask(loggedInTenant, payload);
    markToolCallAsDone(taskId, ToolCallName.EDIT_AGENT_SCHEMA);

    if (!redirectToPlaygrounds) {
      redirectWithParams({
        params: {
          newTaskName: task.name,
          newTaskId: task.id,
          newTaskSchemaId: task.schema_id,
          newTenantId: loggedInTenant,
          newTaskModalOpen: undefined,
          mode: undefined,
          redirectToPlaygrounds: undefined,
        },
        scroll: false,
      });
      return;
    }

    if (task.id && task.schema_id) {
      router.push(
        taskSchemaRoute(
          loggedInTenant ?? (TENANT_PLACEHOLDER as TenantID),
          task.id as TaskID,
          `${task.schema_id}` as TaskSchemaID
        )
      );
      return;
    }

    onClose();
  }, [
    loggedInTenant,
    computedInputSchema,
    computedOutputSchema,
    taskName,
    createTask,
    updateTaskSchema,
    fetchTaskSchema,
    fetchTask,
    taskSchemaId,
    router,
    onClose,
    taskId,
    isEditMode,
    messages,
    redirectWithParams,
    redirectToPlaygrounds,
    pathname,
    markToolCallAsDone,
  ]);

  const isMounted = useIsMounted();

  const [abortController, setAbortController] = useState<AbortController | undefined>(undefined);

  const onSendIteration = useCallback(
    async (suggestion?: string) => {
      const abortController = new AbortController();
      setAbortController(abortController);

      setShowRetry(false);

      const newMessage = suggestion || userMessage;
      if (!newMessage) return;

      // We add an initial message if this is the first iteration to take into account the edited task schema or the default one
      const request = {
        previous_iterations: computeSendIterationPreviousIterations(
          previousIterations,
          computedInputSchema,
          computedOutputSchema
        ),
        user_message: newMessage,
      };
      setUserMessage('');
      setMessages((prev) => [
        ...prev,
        {
          message: newMessage,
          username: fullName || 'You',
          date: new Date(),
          imageUrl: userImageUrl,
        },
      ]);
      setLoading(true);

      try {
        const newIteration = await iterateTaskInputOutput(
          loggedInTenant,
          request,
          token,
          (data) => {
            if (!isMounted() || !open) return;

            setStreamingMessage({
              message: data.assistant_answer,
              username: WORKFLOW_AI_USERNAME,
              date: new Date(),
              streamed: true,
            });

            setStreamedIteration(data);
          },
          abortController?.signal
        );

        if (abortController?.signal.aborted) {
          setStreamingMessage(undefined);
          setStreamedIteration(undefined);
          setShowRetry(false);
          return;
        }

        if (!isMounted() || !open) return;

        setStreamingMessage(undefined);
        setStreamedIteration(undefined);

        setPreviousIterations((prev) => [...prev, newIteration]);
        setMessages((prev) => [
          ...prev,
          {
            message: newIteration.assistant_answer,
            username: WORKFLOW_AI_USERNAME,
            date: new Date(),
          },
        ]);
      } catch (err: unknown) {
        displayErrorToaster('Error iterating AI agent');
        setStreamingMessage(undefined);
        setStreamedIteration(undefined);
        setShowRetry(true);
        console.error(`Error iterating AI agent: ${err}`);
      } finally {
        setLoading(false);
      }
    },
    [
      userMessage,
      previousIterations,
      fullName,
      userImageUrl,
      iterateTaskInputOutput,
      loggedInTenant,
      isMounted,
      computedInputSchema,
      computedOutputSchema,
      open,
      token,
      setShowRetry,
    ]
  );

  const [showConfirmModal, toggleConfirmModal] = useToggle(false);
  const onConfirmClose = useCallback(() => {
    toggleConfirmModal();
    cancelToolCall(ToolCallName.EDIT_AGENT_SCHEMA);
    onClose();
  }, [toggleConfirmModal, onClose, cancelToolCall]);

  const onCloseRequest = useCallback(() => {
    if (!isEditMode && messages.length === 0 && !userMessage) {
      // TODO: there is a weird issue where currentTaskSchema is the task for the URL
      // when in creation mode.
      cancelToolCall(ToolCallName.EDIT_AGENT_SCHEMA);
      onClose();
      return;
    }

    if (
      messages.length > 1 ||
      !!userMessage ||
      !areSchemasEquivalent(computedInputSchema as JsonSchema, inputSchemaForVariant) ||
      !areSchemasEquivalent(computedOutputSchema as JsonSchema, outputSchemaForVariant)
    ) {
      toggleConfirmModal();
    } else {
      cancelToolCall(ToolCallName.EDIT_AGENT_SCHEMA);
      onClose();
    }
  }, [
    messages.length,
    userMessage,
    computedInputSchema,
    inputSchemaForVariant,
    outputSchemaForVariant,
    isEditMode,
    computedOutputSchema,
    onClose,
    toggleConfirmModal,
    cancelToolCall,
  ]);

  const firstMessageDisplay = useMemo(
    () => ({
      username: WORKFLOW_AI_USERNAME,
      date: new Date(),
      message: `Hi${userFirstName ? ` ${userFirstName}` : ''}, ${isEditMode ? "you have two ways to edit your AI agent schema:\n\n1. Type your edit request in a message to me, and I'll handle the update for you.\n2. If you prefer, you can directly edit the AI agent schema on the left yourself.\n\nYou can even to use a combination of both if that best suits your needs!" : 'what would you like to do today?'}`,
    }),
    [userFirstName, isEditMode]
  );

  const abortControllerRef = useRef<AbortController | undefined>(undefined);
  abortControllerRef.current = abortController;

  const prefilledMessageWasSend = useRef(false);

  useEffect(() => {
    if (
      !prefilledMessageWasSend.current &&
      !!prefilledMessage &&
      open &&
      !!previousIterations &&
      !!computedInputSchema &&
      !!computedOutputSchema &&
      previousIterations.length > 0
    ) {
      prefilledMessageWasSend.current = true;
      setTimeout(() => {
        onSendIteration(prefilledMessage);
      }, 1000);
    }
  }, [
    onSendIteration,
    prefilledMessage,
    computedInputSchema,
    computedOutputSchema,
    open,
    previousIterations,
    inputSchemaForVariant,
    outputSchemaForVariant,
  ]);

  useEffect(() => {
    if (!open) {
      abortControllerRef.current?.abort();
      setInputSplattedSchema(undefined);
      setOutputSplattedSchema(undefined);
      setPreviousIterations([]);
      setStreamedIteration(undefined);
      setMessages([]);
      setStreamingMessage(undefined);
      setUserMessage('');
      setLoading(false);
      prefilledMessageWasSend.current = false;
      return;
    } else if (isEditMode) {
      setMessages([firstMessageDisplay]);
    }
  }, [open, isEditMode, firstMessageDisplay]);

  const taskNameRef = useRef(taskName);
  taskNameRef.current = taskName;

  useEffect(() => {
    if (!inputSchemaForVariant || !outputSchemaForVariant || !taskNameRef.current || !isEditMode) {
      return;
    }

    setPreviousIterations([
      {
        task_schema: {
          task_name: taskNameRef.current,
          input_json_schema: inputSchemaForVariant as Record<string, unknown>,
          output_json_schema: outputSchemaForVariant as Record<string, unknown>,
        },
        user_message: '',
        assistant_answer: INITIAL_ASSISTANT_MESSAGE,
      },
    ]);
  }, [taskNameRef, inputSchemaForVariant, outputSchemaForVariant, isEditMode, open, firstMessageDisplay]);

  const featureWasSelected = useCallback(
    (
      title: string,
      inputSchema: Record<string, unknown>,
      outputSchema: Record<string, unknown>,
      message: string | undefined
    ) => {
      setPreviousIterations([
        {
          task_schema: {
            task_name: title,
            input_json_schema: inputSchema,
            output_json_schema: outputSchema,
          },
          user_message: message ?? '',
          assistant_answer: INITIAL_ASSISTANT_MESSAGE,
        },
      ]);

      const messages: ConversationMessage[] = [];

      if (message) {
        messages.push({
          message: message,
          username: 'You',
          date: new Date(),
        });
      }

      messages.push({
        message: INITIAL_ASSISTANT_MESSAGE,
        username: WORKFLOW_AI_USERNAME,
        date: new Date(),
      });

      setMessages(messages);
    },
    []
  );

  const isFullMessageView = !isEditMode && !inputSplattedSchema && !outputSplattedSchema;
  const isSaveButtonHidden = isFullMessageView;

  const { checkIfAllowed } = useIsAllowed();

  useEffect(() => {
    if (open && isEditMode && !checkIfAllowed()) {
      onClose();
    }
  }, [open, checkIfAllowed, onClose, isEditMode]);

  const onRetry = useCallback(() => {
    const lastMessage = messages.pop();
    const text = lastMessage?.message?.toString();
    if (lastMessage) {
      setMessages(messages);
    }

    setShowRetry(false);
    onSendIteration(text);
  }, [onSendIteration, messages]);

  return (
    <Dialog open={open} onOpenChange={onCloseRequest}>
      <DialogContent className='min-w-[90vw] h-[90vh] p-0'>
        <div className='flex flex-col h-full w-full overflow-hidden bg-custom-gradient-1 rounded-[3px]'>
          <NewTaskModalHeader
            onClose={onCloseRequest}
            onSave={noChangesDetected ? undefined : onSave}
            onSendIteration={isFullMessageView ? onSendIteration : undefined}
            isSaveButtonHidden={isSaveButtonHidden}
            mode={mode}
            isRedirecting={redirectToPlaygrounds}
          />
          {mode === 'editDescription' ? (
            <DescriptionExampleEditor
              inputSplattedSchema={inputSplattedSchema}
              setInputSplattedSchema={setInputSplattedSchema}
              outputSplattedSchema={outputSplattedSchema}
              setOutputSplattedSchema={setOutputSplattedSchema}
            />
          ) : (
            <NewTaskModalContent
              isInitialized={isEditMode ? taskSchemaInitialized : true}
              isEditMode={isEditMode}
              inputSplattedSchema={inputSplattedSchema}
              setInputSplattedSchema={setInputSplattedSchema}
              outputSplattedSchema={outputSplattedSchema}
              setOutputSplattedSchema={setOutputSplattedSchema}
              loading={loading}
              userMessage={userMessage}
              messages={allMessages}
              setUserMessage={setUserMessage}
              onSendIteration={onSendIteration}
              userFirstName={userFirstName}
              open={open}
              computedInputSchema={computedInputSchema as JsonSchema}
              computedOutputSchema={computedOutputSchema as JsonSchema}
              noChangesDetected={noChangesDetected}
              tenant={tenant}
              taskSchemaId={taskSchemaId}
              token={token}
              showRetry={showRetry}
              retry={onRetry}
              featureWasSelected={featureWasSelected}
            />
          )}
          <AlertDialog
            open={showConfirmModal}
            title={isEditMode ? 'Confirm Cancellation' : 'Leave AI Agent Creation?'}
            text={
              isEditMode
                ? 'You haven’t saved your recent edits. Are you sure you want to cancel them?'
                : 'Are you sure you want to discard the changes and leave the AI agent creation?'
            }
            confrimationText='Cancel Changes'
            cancelText='Go Back'
            onCancel={toggleConfirmModal}
            onConfirm={onConfirmClose}
            destructive
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
