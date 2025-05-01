import { Settings16Regular, StopRegular } from '@fluentui/react-icons';
import { Wand16Regular } from '@fluentui/react-icons';
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';

type GenerateInputControlsProps = {
  onQuickGenerateInput: () => void;
  inputLoading: boolean;
  singleTaskLoading: boolean;
  areInstructionsLoading: boolean;
  toggleSettingsModal: () => void;
  onStopGeneratingInput: () => void;
};

export function GenerateInputControls(props: GenerateInputControlsProps) {
  const {
    onQuickGenerateInput,
    inputLoading,
    singleTaskLoading,
    areInstructionsLoading,
    toggleSettingsModal,
    onStopGeneratingInput,
  } = props;

  const [isHovering, setIsHovering] = useState(false);
  const shouldShowStopGenerating = isHovering && inputLoading;

  const text = inputLoading ? 'Generating Input...' : 'Generate Input';

  return (
    <div className='flex flex-row' onMouseEnter={() => setIsHovering(true)} onMouseLeave={() => setIsHovering(false)}>
      {shouldShowStopGenerating ? (
        <Button
          variant='newDesign'
          icon={<StopRegular className='h-4 w-4' />}
          size='none'
          className='rounded-none rounded-l-[2px] h-7 px-2 text-xs mr-0 border-r-0'
          onClick={onStopGeneratingInput}
        >
          Stop Generating
        </Button>
      ) : (
        <SimpleTooltip asChild content='Use AI to generate realistic input'>
          <Button
            variant='newDesign'
            icon={<Wand16Regular className='h-4 w-4' />}
            onClick={onQuickGenerateInput}
            loading={inputLoading}
            disabled={singleTaskLoading || areInstructionsLoading}
            size='none'
            className='rounded-none rounded-l-[2px] h-7 px-2 text-xs mr-0 border-r-0'
          >
            {text}
          </Button>
        </SimpleTooltip>
      )}

      <SimpleTooltip asChild content='Customize the input you want generated'>
        <Button
          variant='newDesign'
          icon={<Settings16Regular className='h-4 w-4' />}
          onClick={toggleSettingsModal}
          size='none'
          disabled={singleTaskLoading || inputLoading || areInstructionsLoading}
          className='rounded-none rounded-tr-[2px] rounded-br-[2px] h-7 w-7'
        />
      </SimpleTooltip>
    </div>
  );
}
