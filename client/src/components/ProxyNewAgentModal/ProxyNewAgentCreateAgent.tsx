import { Dismiss12Regular } from '@fluentui/react-icons';
import { nanoid } from 'nanoid';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useRedirectWithParams } from '@/lib/queryString';
import { taskSchemaRoute } from '@/lib/routeFormatter';
import { useOrFetchNewAgentChat } from '@/store/new_agent_messages';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { Button } from '../ui/Button';
import { ProxyNewAgentCreateAgentChat } from './ProxyNewAgentCreateAgentChat';
import { ProxyNewAgentCreateAgentFirstMessageEntry } from './ProxyNewAgentCreateAgentFirstMessageEntry';

type Props = {
  tenant: TenantID | undefined;
};

export function ProxyNewAgentCreateAgent(props: Props) {
  const { tenant } = props;

  const redirectWithParams = useRedirectWithParams();

  const onClose = useCallback(() => {
    redirectWithParams({ params: { mode: undefined, addAgent: undefined } });
  }, [redirectWithParams]);

  const chatId = useMemo(() => nanoid(), []);

  const { messages, isLoading, sendMessage, showRetry, retry, agentCreationResult } = useOrFetchNewAgentChat(
    chatId,
    tenant
  );

  const router = useRouter();
  const redirectInProgressRef = useRef(false);

  useEffect(() => {
    redirectInProgressRef.current = false;
  }, [chatId]);

  useEffect(() => {
    if (!agentCreationResult) {
      return;
    }

    if (redirectInProgressRef.current) {
      return;
    }

    redirectInProgressRef.current = true;

    const taskId = agentCreationResult.agent_id as TaskID;
    const taskSchemaId = `${agentCreationResult.agent_schema_id}` as TaskSchemaID;

    const route = taskSchemaRoute(tenant as TenantID, taskId, taskSchemaId, {
      versionId: agentCreationResult.version_id,
      taskRunId1: agentCreationResult.run_id,
      baseRunId: agentCreationResult.run_id,
    });

    router.push(route);
  }, [agentCreationResult, redirectWithParams, tenant, router]);

  return (
    <div className='flex flex-col h-full w-full overflow-hidden bg-custom-gradient-1 rounded-[3px]'>
      <div className='flex items-center px-4 justify-between h-[54px] flex-shrink-0 border-b border-gray-200 border-dashed'>
        <div className='flex items-center py-1 gap-4 text-gray-900 text-[16px] font-semibold font-lato'>
          <Button
            onClick={onClose}
            variant='newDesign'
            icon={<Dismiss12Regular className='w-3 h-3' />}
            className='w-7 h-7'
            size='none'
          />
          New AI Agent
        </div>
      </div>
      <div className='flex flex-row items-center justify-center w-full h-[calc(100%-54px)] overflow-hidden'>
        {!!messages && messages?.length > 0 ? (
          <ProxyNewAgentCreateAgentChat
            sendMessage={sendMessage}
            messages={messages}
            isLoading={isLoading}
            showRetry={showRetry}
            onRetry={retry}
          />
        ) : (
          <ProxyNewAgentCreateAgentFirstMessageEntry sendMessage={sendMessage} />
        )}
      </div>
    </div>
  );
}
