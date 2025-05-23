import { StreamOutputRegular } from '@fluentui/react-icons';
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { DialogContent } from '@/components/ui/Dialog';
import { Dialog } from '@/components/ui/Dialog';
import { ProxyMessageContent } from '@/types/workflowAI';
import { ToolCallRequestWithID } from '@/types/workflowAI/models';
import { ProxyEditToolCallRequest } from './ProxyEditToolCallRequest';

type Props = {
  content: ProxyMessageContent;
  setContent: (content: ProxyMessageContent) => void;
  readonly?: boolean;
};

export function ProxyToolCallRequest(props: Props) {
  const { content, setContent, readonly } = props;

  const request = content.tool_call_request;
  const dictText = useMemo(() => JSON.stringify(request?.tool_input_dict), [request?.tool_input_dict]);

  const [isHovering, setIsHovering] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  const setRequest = (request: ToolCallRequestWithID | undefined) => {
    setContent({
      ...content,
      tool_call_request: request,
    });
  };

  if (!request) {
    return null;
  }

  return (
    <div
      className='flex flex-row w-full items-center justify-between relative'
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      <div className='flex flex-col'>
        <div className='flex items-center justify-between px-1'>
          <div className='flex items-center gap-2 text-gray-700 text-xsm'>
            <StreamOutputRegular className='w-4 h-4 text-gray-400' />
            Tool Call Request
          </div>
        </div>
        <div className='pl-6 py-2'>
          <div className='flex flex-col text-gray-700 text-xsm border-l px-3 gap-2'>
            <div className='flex flex-col'>
              <div className='font-medium'>{request?.tool_name}</div>
              <div>{dictText}</div>
            </div>
          </div>
        </div>
      </div>
      {isHovering && !readonly && (
        <div className='absolute right-0 top-[50%] -translate-y-1/2 flex items-center justify-center gap-2'>
          <Button variant='newDesign' size='sm' onClick={() => setIsEditModalOpen(true)}>
            Edit
          </Button>
        </div>
      )}

      {isEditModalOpen && (
        <Dialog open={!!isEditModalOpen} onOpenChange={() => setIsEditModalOpen(false)}>
          <DialogContent className='max-w-[90vw] max-h-[90vh] w-[672px] p-0 overflow-hidden bg-custom-gradient-1 rounded-[2px] border border-gray-300'>
            <ProxyEditToolCallRequest
              request={request}
              setRequest={setRequest}
              onClose={() => setIsEditModalOpen(false)}
            />
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
