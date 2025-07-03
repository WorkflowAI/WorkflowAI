'use client';

import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { NEW_PROXY_AGENT_MODAL_OPEN, useQueryParamModal } from '@/lib/globalModal';
import { useTaskParams } from '@/lib/hooks/useTaskParams';
import { useParsedSearchParams } from '@/lib/queryString';
import { ProxyNewAgentCreateAgent } from './ProxyNewAgentCreateAgent';
import { ProxyNewAgentModalContent } from './ProxyNewAgentModalContent';

export type ProxyNewAgentModalQueryParams = {
  mode?: 'add' | 'create';
};

const searchParams: (keyof ProxyNewAgentModalQueryParams)[] = ['mode'];

export function useProxyNewAgentModal() {
  return useQueryParamModal<ProxyNewAgentModalQueryParams>(NEW_PROXY_AGENT_MODAL_OPEN, searchParams);
}

export function ProxyNewAgentModal() {
  const { open, closeModal: onClose } = useProxyNewAgentModal();
  const { tenant } = useTaskParams();

  const { mode: mode } = useParsedSearchParams('mode');

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className='min-w-[90vw] h-[90vh] max-h-[800px] p-0 z-20 overflow-hidden'>
        {mode === 'create' ? (
          <ProxyNewAgentCreateAgent tenant={tenant} />
        ) : (
          <ProxyNewAgentModalContent onClose={onClose} tenant={tenant} />
        )}
      </DialogContent>
    </Dialog>
  );
}
