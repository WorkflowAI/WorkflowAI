import { Checkmark20Regular, Play20Regular, Stop20Regular } from '@fluentui/react-icons';
import { useCallback, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';

type Props = {
  onRun: () => void;
  onStopRun: () => void;
  isRunning: boolean;
  disabled: boolean;
  containsError: boolean;
  wasRunSuccessfull: boolean;
};

export function CreateTaskRunButton(props: Props) {
  const { onRun, onStopRun, isRunning, disabled, containsError, wasRunSuccessfull } = props;

  const onClick = useCallback(() => {
    if (isRunning) {
      return;
    }
    onRun();
  }, [onRun, isRunning]);

  const onStop = useCallback(() => {
    if (!isRunning) {
      return;
    }
    onStopRun();
  }, [onStopRun, isRunning]);

  const renderIcon = () => {
    if (containsError) {
      return <Play20Regular className='h-5 w-5' />;
    }

    if (!isRunning) {
      if (wasRunSuccessfull) {
        return <Checkmark20Regular className='h-5 w-5' />;
      } else {
        return <Play20Regular className='h-5 w-5' />;
      }
    }
    return undefined;
  };

  const renderTooltip = () => {
    if (isRunning) {
      return undefined;
    }
    return 'Try Prompt';
  };

  const [isHovering, setIsHovering] = useState(false);

  const normalButtonContent = (
    <SimpleTooltip asChild content={renderTooltip()}>
      <Button
        variant='newDesign'
        size='none'
        loading={isRunning}
        disabled={disabled}
        onClick={onClick}
        icon={renderIcon()}
        className='w-9 h-9'
      />
    </SimpleTooltip>
  );

  const stopButtonContent = (
    <SimpleTooltip asChild content='Stop Run' tooltipDelay={100}>
      <Button
        variant='newDesign'
        size='none'
        onClick={onStop}
        icon={<Stop20Regular className='h-5 w-5 text-gray-800' />}
        className='w-9 h-9'
      />
    </SimpleTooltip>
  );

  return (
    <div onMouseEnter={() => setIsHovering(true)} onMouseLeave={() => setIsHovering(false)}>
      {isHovering && isRunning ? stopButtonContent : normalButtonContent}
    </div>
  );
}
