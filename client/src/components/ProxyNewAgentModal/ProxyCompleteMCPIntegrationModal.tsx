'use client';

import { CursorPromptContent } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/output/CursorPromptContent';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { COMPLETE_PROXY_MCP_INTEGRATION_MODAL_OPEN, useQueryParamModal } from '@/lib/globalModal';
import { useCopy } from '@/lib/hooks/useCopy';
import { Button } from '../ui/Button';

export type ProxyCompleteMCPIntegrationModalQueryParams = {
  integrationURL?: string;
};

const searchParams: (keyof ProxyCompleteMCPIntegrationModalQueryParams)[] = ['integrationURL'];

type ProxyCompleteMCPIntegrationModalPromptProps = {
  title: string;
  description: string;
  text: string;
};

export function ProxyCompleteMCPIntegrationModalPrompt(props: ProxyCompleteMCPIntegrationModalPromptProps) {
  const { title, description, text } = props;

  const onCopy = useCopy();

  const onCopyPrompt = () => {
    onCopy(text, {
      successMessage: 'Prompt was copied',
    });
  };

  return (
    <div className='flex flex-col p-4 w-full bg-white rounded-[2px] border border-gray-200'>
      <div className='flex flex-row items-center justify-between'>
        <div className='flex flex-col'>
          <div className='text-gray-900 text-[16px] font-semibold'>{title}</div>
          <div className='text-gray-500 text-[13px] font-normal'>{description}</div>
        </div>
        <Button onClick={onCopyPrompt} variant='newDesignGray' size='sm'>
          Copy Prompt
        </Button>
      </div>
      <div className='pt-4'>
        <div className='flex py-4 max-w-full bg-custom-gradient-1 rounded-[2px] border border-gray-200 items-center justify-center px-10'>
          <CursorPromptContent text={text} className='w-full' />
        </div>
      </div>
    </div>
  );
}

export function useProxyCompleteMCPIntegrationModal() {
  return useQueryParamModal<ProxyCompleteMCPIntegrationModalQueryParams>(
    COMPLETE_PROXY_MCP_INTEGRATION_MODAL_OPEN,
    searchParams
  );
}

const firstPrompt = 'I want to use WorkflowAI to build a feature that extracts flights information from an email';
const secondPrompt = 'Migrate this agent to WorkflowAI';

export function ProxyCompleteMCPIntegrationModal() {
  const { open, closeModal: onClose } = useProxyCompleteMCPIntegrationModal();

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className='max-w-[90vw] w-[672px] max-h-[90vh] p-0 z-20 overflow-hidden'>
        <div className='flex flex-col h-full w-full overflow-hidden bg-custom-gradient-1 rounded-[3px]'>
          <div className='flex items-center px-4 justify-end h-[54px] flex-shrink-0 border-b border-gray-200 border-dashed'>
            <div className='flex items-center gap-2'>
              <Button variant='newDesignIndigo'>Done</Button>
            </div>
          </div>
          <div className='flex flex-col items-center justify-center w-full h-[calc(100%-54px)] overflow-hidden'>
            <div className='font-semibold text-[18px] text-gray-900 pt-10'>Tap Done to Complete your Set Up</div>
            <div className='font-normal text-[16px] text-gray-400'>Use these prompts to get started:</div>
            <div className='flex flex-col gap-5 pt-5 pb-9 w-full px-10'>
              <ProxyCompleteMCPIntegrationModalPrompt
                title='Create New AI Agent'
                description='Our AI Engineer helps you create new agents effortlessly'
                text={firstPrompt}
              />
              <ProxyCompleteMCPIntegrationModalPrompt
                title='Import Existing AI Agent'
                description='Our AI Engineer helps you create new agents effortlessly'
                text={secondPrompt}
              />
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
