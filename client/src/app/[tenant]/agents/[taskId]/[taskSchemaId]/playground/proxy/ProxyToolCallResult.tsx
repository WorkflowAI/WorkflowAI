import { StreamOutputRegular } from '@fluentui/react-icons';
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { ProxyEditToolCallResult } from './ProxyEditToolCallResult';
import { ProxyMessageContent, ToolCallResult } from './utils';

type Props = {
  result: ToolCallResult;
  setContent: (content: ProxyMessageContent) => void;
  onRemove: () => void;
};

export function ProxyToolCallResult(props: Props) {
  const { result, setContent, onRemove } = props;

  const dictText = useMemo(() => JSON.stringify(result.result), [result.result]);

  const [isHovering, setIsHovering] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  const setResult = (result: ToolCallResult | undefined) => {
    setContent({
      ...result,
      tool_call_result: result,
    });
  };

  if (!result.result) {
    return null;
  }

  return (
    <div
      className='flex flex-row w-full items-center justify-between'
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      <div className='flex flex-col'>
        <div className='flex items-center justify-between px-1'>
          <div className='flex items-center gap-2 text-gray-700 text-xsm'>
            <StreamOutputRegular className='w-4 h-4 text-gray-400' />
            Tool Call Result
          </div>
        </div>
        <div className='pl-6 py-2'>
          <div className='flex flex-col text-gray-700 text-xsm border-l px-3 gap-2'>{dictText}</div>
        </div>
      </div>
      {isHovering && (
        <div className='flex items-center justify-center gap-2'>
          <Button variant='newDesign' size='sm' onClick={() => setIsEditModalOpen(true)}>
            Edit
          </Button>
          <Button variant='destructive' size='sm' onClick={onRemove}>
            Remove
          </Button>
        </div>
      )}

      {isEditModalOpen && (
        <Dialog open={!!isEditModalOpen} onOpenChange={() => setIsEditModalOpen(false)}>
          <DialogContent className='max-w-[90vw] max-h-[90vh] w-[672px] p-0 overflow-hidden bg-custom-gradient-1 rounded-[2px] border border-gray-300'>
            <ProxyEditToolCallResult result={result} setResult={setResult} onClose={() => setIsEditModalOpen(false)} />
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
