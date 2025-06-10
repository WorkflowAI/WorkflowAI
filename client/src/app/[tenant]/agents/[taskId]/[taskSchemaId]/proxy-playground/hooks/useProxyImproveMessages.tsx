import { useCallback, useMemo, useRef, useState } from 'react';
import { ImproveVersionMessagesResponse, useImproveVersionMessages } from '@/store/improve_version_messages';
import { ToolCallName, usePlaygroundChatStore } from '@/store/playgroundChatStore';
import { TaskID, TenantID } from '@/types/aliases';
import { ProxyMessage } from '@/types/workflowAI';

type Props = {
  taskId: TaskID;
  tenant: TenantID | undefined;
  versionId: string | undefined;
  proxyMessages: ProxyMessage[] | undefined;
  setProxyMessages: (proxyMessages: ProxyMessage[] | undefined) => void;
};

export type ProxyImproveMessagesControls = {
  improveVersionMessages: (improvementInstructions: string) => Promise<void>;
  acceptChanges: () => void;
  undoChanges: () => void;
  cancelImprovement: () => void;
  oldProxyMessages: ProxyMessage[] | undefined;
  changelog: string[] | undefined;
  isImproving: boolean;
  showDiffs: boolean;
  setShowDiffs: (showDiffs: boolean) => void;
  showDiffChangelog: boolean;
};

export function useProxyImproveMessages(props: Props): ProxyImproveMessagesControls {
  const { taskId, tenant, versionId, proxyMessages, setProxyMessages } = props;

  const [changelog, setChangelog] = useState<string[] | undefined>(undefined);
  const [oldProxyMessages, setOldProxyMessages] = useState<ProxyMessage[] | undefined>(undefined);
  const [isImproving, setIsImproving] = useState(false);
  const [showDiffs, setShowDiffs] = useState(false);

  const showDiffChangelog = useMemo(() => {
    if (!oldProxyMessages) {
      return false;
    }
    return (changelog && changelog.length > 0) || !isImproving;
  }, [changelog, oldProxyMessages, isImproving]);

  const improve = useImproveVersionMessages((state) => state.improveVersionMessages);

  const abortControllerRef = useRef<AbortController | undefined>(undefined);

  const { markToolCallAsDone, cancelToolCall } = usePlaygroundChatStore();

  const improveVersionMessages = useCallback(
    async (improvementInstructions: string) => {
      if (!versionId) {
        return;
      }

      abortControllerRef.current?.abort();
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      setShowDiffs(true);

      const previouseProxyMessages = proxyMessages;
      if (!oldProxyMessages) {
        setOldProxyMessages(previouseProxyMessages);
      }

      setIsImproving(true);

      const onMessage = (message: ImproveVersionMessagesResponse) => {
        setChangelog(message.changelog);
        setProxyMessages(message.improved_messages);
      };

      try {
        const message = await improve(
          tenant,
          taskId,
          versionId,
          improvementInstructions,
          proxyMessages,
          onMessage,
          abortController.signal
        );

        setChangelog(message.changelog);
        setProxyMessages(message.improved_messages);
        setIsImproving(false);
        markToolCallAsDone(taskId, ToolCallName.IMPROVE_VERSION_MESSAGES);
        return;
      } catch (error) {
        console.error(error);

        cancelToolCall(ToolCallName.IMPROVE_VERSION_MESSAGES);
        setChangelog(undefined);
        setProxyMessages(previouseProxyMessages);
        setOldProxyMessages(undefined);
        setIsImproving(false);
        setShowDiffs(false);
        return;
      }
    },
    [
      improve,
      tenant,
      taskId,
      versionId,
      proxyMessages,
      oldProxyMessages,
      setProxyMessages,
      cancelToolCall,
      markToolCallAsDone,
    ]
  );

  const acceptChanges = useCallback(() => {
    setOldProxyMessages(undefined);
    setChangelog(undefined);
    setShowDiffs(false);
  }, []);

  const undoChanges = useCallback(() => {
    setProxyMessages(oldProxyMessages);
    setOldProxyMessages(undefined);
    setChangelog(undefined);
    setShowDiffs(false);
  }, [setProxyMessages, oldProxyMessages, setChangelog]);

  const cancelImprovement = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = undefined;
  }, []);

  return {
    improveVersionMessages,
    acceptChanges,
    undoChanges,
    cancelImprovement,
    oldProxyMessages,
    changelog,
    isImproving,
    showDiffs,
    setShowDiffs,
    showDiffChangelog,
  };
}
