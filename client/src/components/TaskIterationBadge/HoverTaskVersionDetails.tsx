import { HoverCardContentProps } from '@radix-ui/react-hover-card';
import { HoverCardContent } from '@radix-ui/react-hover-card';
import { useParams } from 'next/navigation';
import { useMemo } from 'react';
import { DebouncedState } from 'usehooks-ts';
import { checkVersionForProxy } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/utils';
import { ProxyVersionDetails } from '@/components/v2/ProxyVersionDetails';
import { TaskVersionDetails } from '@/components/v2/TaskVersionDetails';
import { useOrFetchVersion } from '@/store/fetchers';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';

type HoverTaskVersionDetailsProps = {
  side?: HoverCardContentProps['side'];
  align?: HoverCardContentProps['align'];
  versionId: string;
  handleUpdateNotes?: DebouncedState<(versionId: string, notes: string) => Promise<void>>;
  setVersionIdForCode?: (versionId: string | undefined) => void;
};

export function HoverTaskVersionDetails(props: HoverTaskVersionDetailsProps) {
  const { side, align, versionId, handleUpdateNotes, setVersionIdForCode } = props;
  const { tenant, taskId } = useParams();

  const { version } = useOrFetchVersion(tenant as TenantID, taskId as TaskID, versionId);

  const isProxy = useMemo(() => {
    return checkVersionForProxy(version);
  }, [version]);

  if (!version) {
    return null;
  }

  return (
    <HoverCardContent
      className='w-fit min-w-[340px] max-w-[660px] h-fit p-0 bg-white overflow-hidden rounded-[2px] border border-gray-200 shadow-md z-[100] animate-in fade-in-0 zoom-in-95 m-1'
      side={side}
      align={align}
    >
      {isProxy ? (
        <ProxyVersionDetails
          version={version}
          handleUpdateNotes={handleUpdateNotes}
          className='w-[430px]'
          setVersionIdForCode={setVersionIdForCode}
        />
      ) : (
        <div className='flex flex-col'>
          <div className='text-gray-700 text-[16px] font-semibold px-4 py-3 border-b border-gray-200 border-dashed'>
            Version Details
          </div>
          <TaskVersionDetails version={version} handleUpdateNotes={handleUpdateNotes} className='max-w-[360px]' />
        </div>
      )}
    </HoverCardContent>
  );
}
