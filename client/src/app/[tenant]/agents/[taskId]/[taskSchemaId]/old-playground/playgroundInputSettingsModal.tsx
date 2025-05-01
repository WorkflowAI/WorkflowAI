'use client';

import { Dismiss12Regular, Wand16Regular } from '@fluentui/react-icons';
import { useCallback, useState } from 'react';
import { TemperatureSelector } from '@/components/TemperatureSelector/TemperatureSelector';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { Textarea } from '@/components/ui/Textarea';

type PlaygroundInputSettingsModalProps = {
  onModalGenerateInput: (instructions: string | undefined, temperature: number) => void;
  toggleModal: () => void;
  open: boolean;
};

export function PlaygroundInputSettingsModal(props: PlaygroundInputSettingsModalProps) {
  const { onModalGenerateInput, toggleModal, open } = props;

  const [instruction, setInstruction] = useState('');
  const [temperature, setTemperature] = useState(0);

  const handleInstructionChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInstruction(e.target.value);
  }, []);

  const handleGenerateInput = useCallback(() => {
    const trimmedInstruction = instruction.trim();
    const instructions = trimmedInstruction !== '' ? trimmedInstruction : undefined;
    onModalGenerateInput(instructions, temperature);
  }, [instruction, onModalGenerateInput, temperature]);

  return (
    <Dialog open={open} onOpenChange={toggleModal}>
      <DialogContent className='flex flex-col w-full max-w-[727px] max-h-[90vh] p-0 bg-custom-gradient-1 overflow-hidden'>
        <div className='flex flex-col h-full font-lato overflow-hidden'>
          <div className='flex gap-4 items-center w-full whitespace-nowrap border-b border-gray-200 border-dashed px-4 py-3'>
            <Button
              onClick={toggleModal}
              variant='newDesign'
              icon={<Dismiss12Regular className='w-3 h-3' />}
              className='w-7 h-7 shrink-0'
              size='none'
            />

            <h1 className='text-base font-semibold text-gray-900'>Input Settings</h1>

            <div className='flex justify-end gap-2 w-full'>
              <Button onClick={handleGenerateInput} variant='newDesign' icon={<Wand16Regular className='h-4 w-4' />}>
                Generate Input
              </Button>
            </div>
          </div>

          <div className='flex flex-col p-4 pb-4 overflow-hidden'>
            <div className='mb-1 text-gray-900 text-[13px] font-medium'>Input instructions</div>

            <Textarea
              className='flex min-h-[80px] font-lato border-gray-200 text-gray-800 overflow-y-auto'
              value={instruction}
              onChange={handleInstructionChange}
              placeholder='Add any specific instructions to generate a AI agent input or leave blank...'
              autoFocus
            />

            <div className='mb-1 text-gray-900 text-[13px] font-medium pt-2.5'>Temperature</div>

            <div className='w-fit'>
              <TemperatureSelector temperature={temperature} setTemperature={setTemperature} />
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
