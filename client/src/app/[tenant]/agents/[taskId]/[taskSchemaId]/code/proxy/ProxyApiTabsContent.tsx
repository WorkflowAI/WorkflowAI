import { useMemo } from 'react';
import { MarkdownMessageTextView } from '@/components/NewTaskModal/MarkdownMessageTextView';
import { environmentsForVersion } from '@/lib/versionUtils';
import { useOrFetchIntegrationsCode } from '@/store/integrations_code';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { Integration, VersionV1 } from '@/types/workflowAI';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  version: VersionV1 | undefined;
  integrationId: string | undefined;
  integrations: Integration[] | undefined;
};

export function ProxyApiTabsContent(props: Props) {
  const { tenant, taskId, taskSchemaId, version, integrationId, integrations } = props;

  const integration = useMemo(() => {
    return integrations?.find((integration) => integration.id === integrationId);
  }, [integrations, integrationId]);

  const environment = useMemo(() => {
    if (!version) {
      return undefined;
    }
    return environmentsForVersion(version)?.[0];
  }, [version]);

  const { code } = useOrFetchIntegrationsCode(tenant, taskId, taskSchemaId, version?.id, integration?.id, environment);

  return (
    <div className='flex flex-col w-full flex-1 overflow-hidden'>
      <div className='flex text-[16px] text-gray-700 font-semibold items-center h-[49px] px-4 border-b border-gray-200 border-dashed flex-shrink-0'>
        {integration?.display_name}
      </div>
      <div className='flex w-full h-[calc(100%-49px)] overflow-y-auto'>
        {!!code ? (
          <div className='flex w-full h-max px-4 py-3'>
            <MarkdownMessageTextView message={code} className='text-[16px]' />
          </div>
        ) : (
          <div className='flex flex-col w-full px-4 py-3'>
            <div className='text-[12px] text-gray-400 italic'>Creating updated documentation</div>
            <div className='flex w-full flex-col gap-2 py-2 animate-pulse'>
              <div className='w-[100%] h-[14px] bg-gradient-to-r from-gray-200 to-gray-300 rounded-[2px]' />
              <div className='w-[100%] h-[14px] bg-gradient-to-r from-gray-200 to-gray-300 rounded-[2px]' />
              <div className='w-[100%] h-[14px] bg-gradient-to-r from-gray-200 to-gray-300 rounded-[2px]' />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
