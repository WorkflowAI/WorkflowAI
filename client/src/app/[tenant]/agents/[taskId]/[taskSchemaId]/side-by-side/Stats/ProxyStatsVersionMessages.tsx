import { useMemo } from 'react';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { ProxyMessage, VersionV1 } from '@/types/workflowAI';
import { ProxyMessagesView } from '../../proxy-playground/proxy-messages/ProxyMessagesView';

type Props = {
  version: VersionV1 | undefined;
  baseVersion: VersionV1 | undefined;
};

export function ProxyStatsVersionMessages(props: Props) {
  const { version, baseVersion } = props;

  const messages = useMemo(() => {
    if (!version) return [];
    return version.properties.messages as ProxyMessage[];
  }, [version]);

  if (version) {
    return (
      <div className='flex flex-col py-2 w-full max-h-[400px] overflow-y-auto'>
        <ProxyMessagesView messages={messages as ProxyMessage[]} />
      </div>
    );
  }

  if (baseVersion) {
    return (
      <div className='flex items-center gap-2 justify-start w-full h-full'>
        <div className='text-gray-900 text-[13px]'>Messages match</div>
        <TaskVersionBadgeContainer
          version={baseVersion}
          showDetails={false}
          showNotes={false}
          showHoverState={false}
          showSchema={true}
          interaction={false}
          showFavorite={false}
        />
      </div>
    );
  }

  return <div className='flex items-center justify-start w-full h-full text-gray-500 text-[16px]'>-</div>;
}
