import {
  Add16Regular,
  ArrowCircleUp16Filled,
  ChevronDown16Regular,
  Cloud16Regular,
  Dismiss12Regular,
  Dismiss16Regular,
  History16Regular,
  Image16Regular,
  Info16Regular,
  Mention16Regular,
  MoreHorizontal16Regular,
} from '@fluentui/react-icons';
import { useMemo, useState } from 'react';
import { ProxyNewAgentMCPFlowContent } from '@/components/ProxyNewAgentModal/ProxyNewAgentMCPFlow';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { useCopy } from '@/lib/hooks/useCopy';
import { environmentsForVersion, formatSemverVersion } from '@/lib/versionUtils';
import { VersionV1 } from '@/types/workflowAI';

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
              <div className='flex w-full justify-between items-center'>
                <div className='text-gray-700 text-[12px] font-medium px-2 py-[3px] bg-gray-200 rounded-[4px]'>
                  New Chat
                </div>
                <div className='text-gray-900 text-[12px] flex items-center gap-3 px-1'>
                  <Add16Regular className='w-4 h-4' />
                  <Cloud16Regular className='w-4 h-4' />
                  <History16Regular className='w-4 h-4' />
                  <MoreHorizontal16Regular className='w-4 h-4' />
                  <Dismiss16Regular className='w-3.5 h-3.5' />
                </div>
              </div>
              <div className='flex flex-col gap-2 w-full h-full bg-white rounded-[8px] border border-gray-300 p-2'>
                <div className='flex gap-[3px] py-0.5 px-1 text-gray-500 border border-gray-200 rounded-[4px] text-[11px] font-medium items-center w-fit'>
                  <Mention16Regular className='w-3.5 h-3.5' />
                  <div className='text-gray-500'>Add Context</div>
                </div>
                <div className='text-gray-800 text-[11px] font-medium px-0.5 pb-3'>{text}</div>
                <div className='flex flex-row justify-between gap-1'>
                  <div className='flex flex-row gap-2 items-center'>
                    <div className='flex flex-row gap-1 bg-gray-100 rounded-full px-2 py-1 items-center'>
                      <div className='text-[13px] font-medium text-gray-400'>∞</div>
                      <div className='text-[11px] font-medium text-gray-500'>Agent</div>
                      <div className='text-[11px] font-medium text-gray-400'>⌘I</div>
                      <ChevronDown16Regular className='w-3 h-3 text-gray-400' />
                    </div>
                    <div className='flex flex-row gap-1 items-center'>
                      <div className='text-indigo-600 text-[11px] font-medium'>claude-4-sonnet</div>
                      <div className='text-indigo-600 text-[8px] font-semibold px-[1px] rounded-[2px] border border-1 border-gray-200 mt-[2px]'>
                        MAX
                      </div>
                      <ChevronDown16Regular className='w-3 h-3 text-gray-400' />
                    </div>
                  </div>
                  <div className='flex flex-row gap-2 items-center'>
                    <Image16Regular className='w-4 h-4 text-gray-600' />
                    <div className='flex gap-1 items-center justify-center w-7 y-7 border-2 border-gray-600 rounded-full'>
                      <ArrowCircleUp16Filled className='w-6 h-6 text-gray-600' />
                    </div>
                  </div>
                </div>
              </div>

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
                <ProxyNewAgentMCPFlowContent />
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </DialogContent>
    </Dialog>
  );
}
