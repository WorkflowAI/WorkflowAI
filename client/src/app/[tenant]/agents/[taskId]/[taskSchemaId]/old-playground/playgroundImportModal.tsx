import { Dismiss12Regular } from '@fluentui/react-icons';
import { useCallback, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { Textarea } from '@/components/ui/Textarea';

type PlaygroundImportModalProps = {
  open: boolean;
  onClose: () => void;
  onImport: (importedInput: string) => Promise<void>;
};

export function PlaygroundImportModal(props: PlaygroundImportModalProps) {
  const { open, onClose, onImport } = props;
  const [importedInput, setImportedInput] = useState('');

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setImportedInput(e.target.value);
  }, []);

  const handleImport = useCallback(async () => {
    onClose();
    await onImport(importedInput);
  }, [importedInput, onImport, onClose]);

  return (
    <Dialog open={open}>
      <DialogContent className='p-0 max-w-[700px] min-h-[550px] bg-custom-gradient-1'>
        <div className='flex flex-col h-full font-lato'>
          <div className='flex gap-4 items-center w-full whitespace-nowrap border-b border-gray-200 border-dashed p-4'>
            <Button
              onClick={onClose}
              variant='newDesign'
              icon={<Dismiss12Regular className='w-3 h-3' />}
              className='w-7 h-7 shrink-0'
              size='none'
            />
            <div className='text-sm font-medium'>Import Input</div>
            <div className='flex justify-end gap-2 w-full'>
              <Button onClick={handleImport} variant='newDesignIndigo' disabled={!importedInput}>
                Import
              </Button>
            </div>
          </div>
          <div className='flex-1 flex flex-col gap-1 px-4 pt-4 pb-4'>
            <Textarea
              placeholder='Paste the content you would like to use as import here...'
              className='flex-1 text-[13px]'
              value={importedInput}
              onChange={handleInputChange}
              autoFocus
            />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
