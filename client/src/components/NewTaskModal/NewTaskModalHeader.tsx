import { ArrowRight16Regular, Dismiss12Regular } from '@fluentui/react-icons';
import { useMemo } from 'react';
import { Button } from '@/components/ui/Button';
import { NewTaskModalQueryParams } from './NewTaskModal';

type NewTaskModalCTAProps = {
  isSaveButtonHidden: boolean;
  mode: NewTaskModalQueryParams['mode'];
  onClose: () => void;
  onSave: (() => Promise<void>) | undefined;
  onSendIteration: (() => void) | undefined;
  isRedirecting: boolean;
};

export function NewTaskModalCTA(props: NewTaskModalCTAProps) {
  const { isSaveButtonHidden, mode, onClose, onSave, onSendIteration, isRedirecting } = props;

  const onClick = useMemo(() => {
    if (onSendIteration) {
      return () => onSendIteration();
    }
    return onSave || onClose;
  }, [onClose, onSave, onSendIteration]);

  const buttonText = useMemo(() => {
    if (mode === 'editDescription') {
      return !!onSave ? 'Save' : 'Done';
    }

    if (isRedirecting) {
      return 'Save and Try in Playground';
    } else {
      return 'Save';
    }
  }, [onSave, mode, isRedirecting]);

  const isButtonDisabled = useMemo(() => {
    if (mode === 'editDescription') {
      return isSaveButtonHidden;
    }
    return isSaveButtonHidden || !onSave;
  }, [isSaveButtonHidden, mode, onSave]);

  const showArrow = mode === 'editDescription';

  if (isSaveButtonHidden) {
    return null;
  }

  return (
    <Button
      onClick={onClick}
      variant='newDesign'
      icon={showArrow && <ArrowRight16Regular className='w-4 h-4' />}
      size='none'
      className='px-3 py-2'
      disabled={isButtonDisabled}
    >
      {buttonText}
    </Button>
  );
}

type NewTaskModalHeaderProps = {
  isSaveButtonHidden: boolean;
  mode: NewTaskModalQueryParams['mode'];
  onClose: () => void;
  onSave: (() => Promise<void>) | undefined;
  onSendIteration: (() => void) | undefined;
  isRedirecting: boolean;
};

export function NewTaskModalHeader(props: NewTaskModalHeaderProps) {
  const { isSaveButtonHidden, mode, onClose, onSave, onSendIteration, isRedirecting } = props;

  const title = useMemo(() => {
    switch (mode) {
      case 'new':
        return 'New AI Feature';
      case 'editSchema':
        return 'Edit Schema';
      case 'editDescription':
        return 'Edit Description and Examples';
    }
  }, [mode]);

  return (
    <div className='flex items-center px-4 justify-between h-[60px] flex-shrink-0'>
      <div className='flex items-center py-1.5 gap-4 text-gray-700 text-base font-medium font-lato'>
        <Button
          onClick={onClose}
          variant='newDesign'
          icon={<Dismiss12Regular className='w-3 h-3' />}
          className='w-7 h-7'
          size='none'
        />
        {title}
      </div>
      <NewTaskModalCTA
        mode={mode}
        onClose={onClose}
        onSave={onSave}
        onSendIteration={onSendIteration}
        isSaveButtonHidden={isSaveButtonHidden}
        isRedirecting={isRedirecting}
      />
    </div>
  );
}
