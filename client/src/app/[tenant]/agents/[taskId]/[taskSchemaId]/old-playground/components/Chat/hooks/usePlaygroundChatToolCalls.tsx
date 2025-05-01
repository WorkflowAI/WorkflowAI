import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useOrFetchMetaAgentMessagesIfNeeded } from '@/store/fetchers';
import { usePlaygroundChatStore } from '@/store/playgroundChatStore';
import { ToolCallName } from '@/store/playgroundChatStore';
import { ModelOptional, TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import {
  EditSchemaToolCall,
  GenerateAgentInputToolCall,
  MetaAgentChatMessage,
  PlaygroundState,
  RunCurrentAgentOnModelsToolCall,
} from '@/types/workflowAI/models';
import { ImprovePromptToolCall } from '@/types/workflowAI/models';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  schemaId: TaskSchemaID;
  playgroundState: PlaygroundState;
  onShowEditSchemaModal: (message?: string) => void;
  improveInstructions: (text: string, runId: string | undefined) => Promise<void>;
  changeModels: (columnsAndModels: { column: number; model: ModelOptional | undefined }[]) => void;
  generateNewInput: (instructions: string | undefined) => Promise<void>;
  onCancelChatToolCallOnPlayground: () => void;
  isAutoRunOn: boolean;
};

export function usePlaygroundChatToolCalls(props: Props) {
  const {
    tenant,
    taskId,
    schemaId,
    playgroundState,
    onShowEditSchemaModal,
    improveInstructions,
    changeModels,
    generateNewInput,
    onCancelChatToolCallOnPlayground,
    isAutoRunOn,
  } = props;

  const {
    isLoading,
    messages,
    sendMessage,
    reset,
    updateStateForToolCallId,
    onStop: onStopMetaAgentMessages,
  } = useOrFetchMetaAgentMessagesIfNeeded(tenant, taskId, schemaId, playgroundState);

  const stopPlaygroundChatStore = usePlaygroundChatStore((state) => state.stop);

  const markToolCallAsInProgress = usePlaygroundChatStore((state) => state.markToolCallAsInProgress);

  const inProgressToolCallIdsByToolCallName = usePlaygroundChatStore(
    (state) => state.inProgressToolCallIdsByToolCallName
  );

  const scheduledPlaygroundStateMessageToSendAfterRuns = usePlaygroundChatStore(
    (state) => state.scheduledPlaygroundStateMessageToSendAfterRuns
  );

  const inProgressToolCallIds = useMemo(() => {
    return new Set(Object.values(inProgressToolCallIdsByToolCallName).filter((id): id is string => id !== undefined));
  }, [inProgressToolCallIdsByToolCallName]);

  const onEditSchema = useCallback(
    (toolCall: EditSchemaToolCall) => {
      const { tool_call_id, edition_request_message } = toolCall;

      if (!tool_call_id || !edition_request_message) {
        return;
      }

      markToolCallAsInProgress(ToolCallName.EDIT_AGENT_SCHEMA, tool_call_id);
      onShowEditSchemaModal(edition_request_message);
    },
    [onShowEditSchemaModal, markToolCallAsInProgress]
  );

  const onImproveInstructions = useCallback(
    (toolCall: ImprovePromptToolCall) => {
      const { tool_call_id, run_id, run_feedback_message } = toolCall;

      if (!tool_call_id || !run_feedback_message) {
        return;
      }

      markToolCallAsInProgress(ToolCallName.IMPROVE_AGENT_INSTRUCTIONS, tool_call_id);

      const improveInstructionsRunId = !!run_id ? run_id : undefined;
      improveInstructions(run_feedback_message, improveInstructionsRunId);
    },
    [improveInstructions, markToolCallAsInProgress]
  );

  const onChangeModels = useCallback(
    (toolCall: RunCurrentAgentOnModelsToolCall) => {
      const { tool_call_id, run_configs } = toolCall;

      if (!tool_call_id || !run_configs) {
        return;
      }

      const columnsAndModels: {
        column: number;
        model: ModelOptional | undefined;
      }[] = [];

      run_configs.forEach((runConfig) => {
        const run_on_column = runConfig.run_on_column;
        if (!run_on_column) {
          return;
        }
        switch (run_on_column) {
          case 'column_1':
            columnsAndModels.push({
              column: 0,
              model: runConfig.model as ModelOptional,
            });
            break;
          case 'column_2':
            columnsAndModels.push({
              column: 1,
              model: runConfig.model as ModelOptional,
            });
            break;
          case 'column_3':
            columnsAndModels.push({
              column: 2,
              model: runConfig.model as ModelOptional,
            });
            break;
          default:
            return;
        }
      });

      markToolCallAsInProgress(ToolCallName.RUN_CURRENT_AGENT_ON_MODELS, tool_call_id);

      changeModels(columnsAndModels);
    },
    [markToolCallAsInProgress, changeModels]
  );

  const onGenerateNewInput = useCallback(
    (toolCall: GenerateAgentInputToolCall) => {
      const { tool_call_id, instructions } = toolCall;

      if (!tool_call_id || !instructions) {
        return;
      }

      markToolCallAsInProgress(ToolCallName.GENERATE_AGENT_INPUT, tool_call_id);
      generateNewInput(instructions);
    },
    [markToolCallAsInProgress, generateNewInput]
  );

  const onIgnoreToolCall = useCallback(
    (toolCallId: string | undefined) => {
      if (!toolCallId) {
        return;
      }
      updateStateForToolCallId(toolCallId, 'user_ignored');
    },
    [updateStateForToolCallId]
  );

  const alreadyAutorunToolCallIds = useRef<Set<string>>(new Set());

  const triggerAction = useCallback(
    (message: MetaAgentChatMessage) => {
      if (!message.tool_call) {
        return;
      }

      switch (message.tool_call.tool_name) {
        case ToolCallName.EDIT_AGENT_SCHEMA:
          onEditSchema(message.tool_call as EditSchemaToolCall);
          break;
        case ToolCallName.IMPROVE_AGENT_INSTRUCTIONS:
          onImproveInstructions(message.tool_call as ImprovePromptToolCall);
          break;
        case ToolCallName.RUN_CURRENT_AGENT_ON_MODELS:
          onChangeModels(message.tool_call as RunCurrentAgentOnModelsToolCall);
          break;
        case ToolCallName.GENERATE_AGENT_INPUT:
          onGenerateNewInput(message.tool_call as GenerateAgentInputToolCall);
          break;
        default:
          return;
      }
    },
    [onEditSchema, onImproveInstructions, onChangeModels, onGenerateNewInput]
  );

  const lastMessageWithNotTriggeredToolCall = useMemo(() => {
    if (!!isLoading || !messages || messages.length === 0) {
      return undefined;
    }

    for (let i = messages.length - 1; i >= 0; i--) {
      const message = messages[i];
      if (
        !!message.tool_call &&
        message.tool_call.status === 'assistant_proposed' &&
        !!message.tool_call.tool_call_id &&
        !alreadyAutorunToolCallIds.current.has(message.tool_call.tool_call_id)
      ) {
        return message;
      }
    }

    return undefined;
  }, [messages, isLoading]);

  const onActionForLastToolCall = useCallback(() => {
    if (!lastMessageWithNotTriggeredToolCall) {
      return;
    }
    triggerAction(lastMessageWithNotTriggeredToolCall);
  }, [lastMessageWithNotTriggeredToolCall, triggerAction]);

  const onIgnoreLastToolCall = useCallback(() => {
    if (!lastMessageWithNotTriggeredToolCall) {
      return;
    }
    onIgnoreToolCall(lastMessageWithNotTriggeredToolCall.tool_call?.tool_call_id);
  }, [lastMessageWithNotTriggeredToolCall, onIgnoreToolCall]);

  useEffect(() => {
    if (!!isLoading || !messages || messages.length === 0 || !isAutoRunOn) {
      return;
    }

    const lastMessage = messages[messages.length - 1];

    if (
      !!lastMessage.tool_call &&
      lastMessage.tool_call.auto_run === true &&
      lastMessage.tool_call.status === 'assistant_proposed' &&
      !!lastMessage.tool_call.tool_call_id
    ) {
      if (alreadyAutorunToolCallIds.current.has(lastMessage.tool_call.tool_call_id)) {
        return;
      }

      alreadyAutorunToolCallIds.current.add(lastMessage.tool_call.tool_call_id);
      triggerAction(lastMessage);
    }
  }, [
    messages,
    onEditSchema,
    onImproveInstructions,
    onChangeModels,
    onGenerateNewInput,
    isLoading,
    triggerAction,
    isAutoRunOn,
  ]);

  const showStop = useMemo(() => {
    if (isLoading) {
      return true;
    }

    if (inProgressToolCallIds.size > 0) {
      return true;
    }

    if (scheduledPlaygroundStateMessageToSendAfterRuns) {
      return true;
    }

    return false;
  }, [isLoading, inProgressToolCallIds, scheduledPlaygroundStateMessageToSendAfterRuns]);

  const onStop = useCallback(async () => {
    if (!showStop) {
      return;
    }

    onCancelChatToolCallOnPlayground();
    onStopMetaAgentMessages();
    stopPlaygroundChatStore();
  }, [showStop, stopPlaygroundChatStore, onStopMetaAgentMessages, onCancelChatToolCallOnPlayground]);

  const onClean = useCallback(() => {
    reset();
    onStop();
  }, [reset, onStop]);

  // Stop when changing task
  useEffect(() => {
    onStop();
  }, [taskId]); // eslint-disable-line react-hooks/exhaustive-deps

  const [userMessage, setUserMessage] = useState('');

  const onSendMessage = useCallback(async () => {
    if (userMessage) {
      const message = userMessage;
      const waitAfterStopping = isLoading;
      await onStop();

      if (waitAfterStopping) {
        await new Promise((resolve) => setTimeout(resolve, 200));
      }

      setUserMessage('');
      await sendMessage(message);
    }
  }, [sendMessage, userMessage, onStop, isLoading]);

  return {
    userMessage,
    setUserMessage,
    isLoading,
    messages,
    onSendMessage,
    onClean,
    inProgressToolCallIds,
    onEditSchema,
    onImproveInstructions,
    onChangeModels,
    onGenerateNewInput,
    onIgnoreToolCall,
    onActionForLastToolCall,
    onIgnoreLastToolCall,
    showStop,
    onStop,
  };
}
