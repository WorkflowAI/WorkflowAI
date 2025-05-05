import { Plus } from 'lucide-react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { isPaymentError } from '@/types/errors';

type ModelOutputErrorInformationProps = {
  errorForModel: Error;
  onOpenChangeModalPopover?: () => void;
};

export function ModelOutputErrorInformation(props: ModelOutputErrorInformationProps) {
  const { errorForModel, onOpenChangeModalPopover } = props;
  const _isPaymentError = isPaymentError(errorForModel);

  return (
    <div className='flex flex-col w-full items-center pt-10 mb-10 sm:mb-0'>
      <AlertTriangle size={20} className='text-gray-400' />
      <div className='pt-4 mx-2 text-gray-700 text-[14px] font-medium'>{errorForModel.name}</div>
      <div className='pt-0.5 mx-2 text-gray-500 text-[12px] text-center whitespace-pre-line'>
        {errorForModel.message}
      </div>
      {!!onOpenChangeModalPopover && !_isPaymentError && (
        <Button
          variant='newDesign'
          icon={<Plus className='h-4 w-4 min-w-4' strokeWidth={3} />}
          onClick={onOpenChangeModalPopover}
          className='hidden sm:flex mt-4 min-w-[50px] font-normal'
        >
          Change Model
        </Button>
      )}
    </div>
  );
}
