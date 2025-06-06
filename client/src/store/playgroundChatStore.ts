import { create } from 'zustand';
import { TaskID } from '@/types/aliases';
import { useMetaAgentChat } from './meta_agent_messages';

export enum ToolCallName {
  IMPROVE_AGENT_INSTRUCTIONS = 'improve_agent_instructions',
  IMPROVE_VERSION_MESSAGES = 'update_version_messages',
  EDIT_AGENT_SCHEMA = 'edit_agent_schema',
  RUN_CURRENT_AGENT_ON_MODELS = 'run_current_agent_on_models',
  GENERATE_AGENT_INPUT = 'generate_agent_input',
}

function playgroundStateMessageForToolCallName(toolCallName: ToolCallName): string {
  switch (toolCallName) {
    case ToolCallName.IMPROVE_AGENT_INSTRUCTIONS:
      return 'Instructions were improved and the agent was re-run with the improved instructions, see new agent_runs.';
    case ToolCallName.IMPROVE_VERSION_MESSAGES:
      return 'Version messages were improved and the agent was re-run with the improved version messages, see new agent_runs.';
    case ToolCallName.EDIT_AGENT_SCHEMA:
      return 'Schema was updated and the agent was re-run with the updated schema, see new agent_runs.';
    case ToolCallName.RUN_CURRENT_AGENT_ON_MODELS:
      return 'Models were updated and agent was re-run with the new models, see new agent_runs.';
    case ToolCallName.GENERATE_AGENT_INPUT:
      return 'Input was generated and the agent was re-run with the new input, see new agent_runs.';
  }
}

interface PlaygroundChatState {
  scheduledPlaygroundStateMessageToSendAfterRuns: string | undefined;
  inProgressToolCallIdsByToolCallName: Record<ToolCallName, string | undefined>;

  waitingForTaskRuns: () => boolean;

  markToolCallAsInProgress: (toolCallName: ToolCallName, toolCallId: string) => void;
  markToolCallAsDone: (taskId: TaskID, toolCallName: ToolCallName) => void;
  cancelToolCall: (toolCallName: ToolCallName) => void;

  getScheduledPlaygroundStateMessageToSendAfterRuns: () => string | undefined;
  markScheduledPlaygroundStateMessageAsSend: () => void;

  stop: () => void;
}

export const usePlaygroundChatStore = create<PlaygroundChatState>()((set, get) => ({
  inProgressToolCallIdsByToolCallName: {
    [ToolCallName.IMPROVE_AGENT_INSTRUCTIONS]: undefined,
    [ToolCallName.IMPROVE_VERSION_MESSAGES]: undefined,
    [ToolCallName.EDIT_AGENT_SCHEMA]: undefined,
    [ToolCallName.RUN_CURRENT_AGENT_ON_MODELS]: undefined,
    [ToolCallName.GENERATE_AGENT_INPUT]: undefined,
  },

  scheduledPlaygroundStateMessageToSendAfterRuns: undefined,

  markToolCallAsInProgress: (toolCallName: ToolCallName, toolCallId: string) => {
    set((state) => ({
      ...state,
      inProgressToolCallIdsByToolCallName: {
        ...state.inProgressToolCallIdsByToolCallName,
        [toolCallName]: toolCallId,
      },
    }));
  },

  cancelToolCall: (toolCallName: ToolCallName) => {
    set((state) => ({
      ...state,
      inProgressToolCallIdsByToolCallName: {
        ...state.inProgressToolCallIdsByToolCallName,
        [toolCallName]: undefined,
      },
    }));
  },

  markToolCallAsDone: (taskId: TaskID, toolCallName: ToolCallName) => {
    const toolCallId = get().inProgressToolCallIdsByToolCallName[toolCallName];

    if (!toolCallId) {
      return;
    }

    useMetaAgentChat.getState().updateStateForToolCallId(taskId, toolCallId, 'completed');
    get().cancelToolCall(toolCallName);

    set((state) => ({
      ...state,
      scheduledPlaygroundStateMessageToSendAfterRuns: playgroundStateMessageForToolCallName(toolCallName),
    }));
  },

  getScheduledPlaygroundStateMessageToSendAfterRuns: () => {
    return get().scheduledPlaygroundStateMessageToSendAfterRuns;
  },

  markScheduledPlaygroundStateMessageAsSend: () => {
    set((state) => ({
      ...state,
      scheduledPlaygroundStateMessageToSendAfterRuns: undefined,
    }));
  },

  waitingForTaskRuns: () => {
    return !!get().scheduledPlaygroundStateMessageToSendAfterRuns;
  },

  stop: () => {
    set((state) => ({
      ...state,
      scheduledPlaygroundStateMessageToSendAfterRuns: undefined,
      inProgressToolCallIdsByToolCallName: {
        [ToolCallName.IMPROVE_AGENT_INSTRUCTIONS]: undefined,
        [ToolCallName.IMPROVE_VERSION_MESSAGES]: undefined,
        [ToolCallName.EDIT_AGENT_SCHEMA]: undefined,
        [ToolCallName.RUN_CURRENT_AGENT_ON_MODELS]: undefined,
        [ToolCallName.GENERATE_AGENT_INPUT]: undefined,
      },
    }));
  },
}));
