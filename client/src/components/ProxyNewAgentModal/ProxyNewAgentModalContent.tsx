import { Dismiss12Regular } from '@fluentui/react-icons';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { useCallback } from 'react';
import { useRedirectWithParams } from '@/lib/queryString';
import { tasksRoute } from '@/lib/routeFormatter';
import { useTasks } from '@/store/task';
import { TenantID } from '@/types/aliases';
import { Button } from '../ui/Button';
import { ProxyNewAgentEndpointFlow } from './ProxyNewAgentEndpointFlow';
import { ProxyNewAgentMCPFlow } from './ProxyNewAgentMCPFlow';

type ProxyNewAgentModalContentProps = {
  onClose: () => void;
  tenant: TenantID;
};

export function ProxyNewAgentModalContent(props: ProxyNewAgentModalContentProps) {
  const { onClose, tenant } = props;
  const router = useRouter();
  const fetchTasks = useTasks((state) => state.fetchTasks);
  const redirectWithParams = useRedirectWithParams();

  const goToDashboard = useCallback(() => {
    fetchTasks(tenant);
    router.push(tasksRoute(tenant));
  }, [router, tenant, fetchTasks]);

  const onCreateAgent = useCallback(() => {
    redirectWithParams({ params: { mode: 'create' } });
  }, [redirectWithParams]);

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
          Add Agent
        </div>
        <div className='flex items-center gap-2'>
          <Button
            onClick={onCreateAgent}
            variant='newDesign'
            icon={
              <Image
                src='https://workflowai.blob.core.windows.net/workflowai-public/GlobeDesktop.png'
                alt='Icon'
                width={16}
                height={16}
              />
            }
          >
            Create an Agent on the Web
          </Button>
          <Button onClick={goToDashboard} variant='newDesignIndigo'>
            Go to Dashboard
          </Button>
        </div>
      </div>
      <div className='flex flex-row items-center justify-center w-full h-[calc(100%-54px)] overflow-hidden'>
        <div className='flex w-[50%] h-full items-center justify-center border-r border-gray-200 overflow-hidden'>
          <ProxyNewAgentMCPFlow />
        </div>
        <div className='flex w-[50%] h-full items-center justify-center overflow-hidden'>
          <ProxyNewAgentEndpointFlow />
        </div>
      </div>
    </div>
  );
}
