import { useMemo } from 'react';
import { MarkdownMessageTextView } from '@/components/NewTaskModal/MarkdownMessageTextView';
import { useOrFetchIntegrationsCode } from '@/store/integrations_code';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { Integration } from '@/types/workflowAI';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  versionId: string | undefined;
  integrationId: string | undefined;
  integrations: Integration[] | undefined;
};

export function ProxyApiTabsContent(props: Props) {
  const { tenant, taskId, taskSchemaId, versionId, integrationId, integrations } = props;

  const integration = useMemo(() => {
    return integrations?.find((integration) => integration.id === integrationId);
  }, [integrations, integrationId]);

  const { code } = useOrFetchIntegrationsCode(tenant, taskId, taskSchemaId, versionId, integration?.id);

  return (
    <div className='flex flex-col w-full h-full'>
      <div className='flex text-[16px] text-gray-700 font-semibold items-center h-[52px] px-4 border-b border-gray-200 border-dashed'>
        {integration?.display_name}
      </div>
      <div className='flex px-4 py-3 w-full h-full'>
        {!!code ? (
          <MarkdownMessageTextView message={code} className='text-[16px] mt-1' />
        ) : (
          <div className='flex flex-col w-full'>
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
