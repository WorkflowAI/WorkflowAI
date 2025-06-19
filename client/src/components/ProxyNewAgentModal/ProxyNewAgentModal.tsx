'use client';

import { Dismiss12Regular } from '@fluentui/react-icons';
import { useRouter } from 'next/navigation';
import { useCallback } from 'react';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { NEW_PROXY_AGENT_MODAL_OPEN, useQueryParamModal } from '@/lib/globalModal';
import { useTaskParams } from '@/lib/hooks/useTaskParams';
import { tasksRoute } from '@/lib/routeFormatter';
import { useTasks } from '@/store/task';
import { Button } from '../ui/Button';
import { ProxyNewAgentEndpointFlow } from './ProxyNewAgentEndpointFlow';
import { ProxyNewAgentMCPFlow } from './ProxyNewAgentMCPFlow';

export type ProxyNewAgentModalQueryParams = {
  mode: 'new';
};

const searchParams: (keyof ProxyNewAgentModalQueryParams)[] = [];

export function useProxyNewAgentModal() {
  return useQueryParamModal<ProxyNewAgentModalQueryParams>(NEW_PROXY_AGENT_MODAL_OPEN, searchParams);
}

export function ProxyNewAgentModal() {
  const { open, closeModal: onClose } = useProxyNewAgentModal();
  const { tenant } = useTaskParams();
  const router = useRouter();
  const fetchTasks = useTasks((state) => state.fetchTasks);

  const goToDashboard = useCallback(() => {
    fetchTasks(tenant);
    router.push(tasksRoute(tenant));
  }, [router, tenant, fetchTasks]);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className='min-w-[90vw] h-[90vh] p-0 z-20 overflow-hidden'>
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
              <Button variant='newDesign' openInNewTab={true} toRoute='https://docs2.workflowai.com/'>
                Manually Set Up
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
      </DialogContent>
    </Dialog>
  );
}
