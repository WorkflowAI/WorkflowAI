import { Checkmark20Regular, Play20Regular, Stop20Regular } from '@fluentui/react-icons';
import { useCallback, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { TaskRunner } from '../hooks/useTaskRunners';

type Props = {
  taskRunner: TaskRunner;
  disabled: boolean;
  containsError: boolean;
};
export function CreateTaskRunButton({ taskRunner, disabled, containsError }: Props) {
  const onClick = useCallback(() => {
    if (taskRunner.loading) {
      return;
    }
    taskRunner.execute();
  }, [taskRunner]);

  const onStop = useCallback(() => {
    if (!taskRunner.loading) {
      return;
    }
    taskRunner.cancel();
  }, [taskRunner]);

  const renderIcon = () => {
    if (containsError) {
      return <Play20Regular className='h-5 w-5' />;
    }
    if (!taskRunner.loading) {
      switch (taskRunner.inputStatus) {
        case 'processed':
          return <Checkmark20Regular className='h-5 w-5' />;
        case 'unprocessed':
          return <Play20Regular className='h-5 w-5' />;
      }
    }
    return undefined;
  };

  const renderTooltip = () => {
    if (taskRunner.loading) {
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
        loading={taskRunner.loading}
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
      {isHovering && taskRunner.loading ? stopButtonContent : normalButtonContent}
    </div>
  );
}
