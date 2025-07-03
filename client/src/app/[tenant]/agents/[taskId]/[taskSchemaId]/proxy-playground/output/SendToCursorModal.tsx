import { Dismiss12Regular, Info16Regular } from '@fluentui/react-icons';
import { useMemo, useState } from 'react';
import { ProxyNewAgentMCPFlowContent } from '@/components/ProxyNewAgentModal/ProxyNewAgentMCPFlow';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { useCopy } from '@/lib/hooks/useCopy';
import { environmentsForVersion, formatSemverVersion } from '@/lib/versionUtils';
import { VersionV1 } from '@/types/workflowAI';
import { CursorPromptContent } from './CursorPromptContent';

type Props = {
  agentId: string;
  version: VersionV1;
  open: boolean;
  onClose: () => void;
};

export function SendToCursorModal(props: Props) {
  const { agentId, version, open, onClose } = props;

  const text = useMemo(() => {
    const versionNumber = formatSemverVersion(version);
    const environment = environmentsForVersion(version)?.[0];
    const versionAndEnvironment = environment ? `${versionNumber}/${environment}` : versionNumber;
    return `Update WorkflowAI agent to version [${versionAndEnvironment}] get_code(agent_id="${agentId}") with the WorkflowAI MCP.`;
  }, [agentId, version]);

  const onCopy = useCopy();

  const onCopyPrompt = () => {
    onCopy(text, {
      successMessage: 'Prompt for Cursor copied',
    });
    onClose();
  };

  const [openCursorIntegration, setOpenCursorIntegration] = useState(false);

  if (!open) {
    return null;
  }

  return (
    <Dialog open={!!open} onOpenChange={onClose}>
      <DialogContent className='w-[416px] p-0 bg-custom-gradient-1 rounded-[2px] border border-gray-300'>
        <div className='flex flex-col h-full w-full overflow-hidden'>
          <div className='flex items-center px-4 justify-between h-[60px] flex-shrink-0 border-b border-gray-200 border-dashed'>
            <div className='flex items-center gap-4 text-gray-900 text-[16px] font-semibold'>
              <Button
                onClick={onClose}
                variant='newDesign'
                icon={<Dismiss12Regular className='w-3 h-3' />}
                className='w-7 h-7'
                size='none'
              />
              Send to Cursor
            </div>
            <Button variant='newDesignIndigo' onClick={onCopyPrompt}>
              Copy Prompt & Close
            </Button>
          </div>
          <div className='flex flex-row w-full h-[calc(100%-60px)] overflow-hidden'>
            <div className='flex flex-col w-full h-full px-4 pt-6 gap-2'>
              <CursorPromptContent text={text} />

              <div className='flex flex-row gap-[6px] px-2 items-center pt-2 pb-4'>
                <Info16Regular className='w-3 h-3 text-gray-500' />
                <div className='text-gray-500 text-[13px]'>
                  {`Don't have a Cursor + WorkflowAI integration yet?`}{' '}
                  <span className='underline cursor-pointer' onClick={() => setOpenCursorIntegration(true)}>
                    Click here
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <Dialog open={!!openCursorIntegration} onOpenChange={setOpenCursorIntegration}>
          <DialogContent className='max-w-[700px] p-0 bg-custom-gradient-1 rounded-[2px] border border-gray-300'>
            <div className='flex flex-col h-full w-full overflow-hidden'>
              <div className='flex items-center px-4 justify-between h-[60px] flex-shrink-0 border-b border-gray-200 border-dashed'>
                <div className='flex items-center gap-4 text-gray-900 text-[16px] font-semibold'>
                  <Button
                    onClick={() => setOpenCursorIntegration(false)}
                    variant='newDesign'
                    icon={<Dismiss12Regular className='w-3 h-3' />}
                    className='w-7 h-7'
                    size='none'
                  />
                  Set up the WorkflowAI MCP Server
                </div>
              </div>
              <div className='flex items-center justify-center p-4'>
                <ProxyNewAgentMCPFlowContent close={onClose} />
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </DialogContent>
    </Dialog>
  );
}
