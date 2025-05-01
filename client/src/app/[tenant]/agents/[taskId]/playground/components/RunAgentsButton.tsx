import { Play16Filled, Save16Filled, Stop16Filled } from '@fluentui/react-icons';
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { cn } from '@/lib/utils';

type Props = {
  showSaveAllVersions: boolean;
  areTasksRunning: boolean;
  inputLoading: boolean;
  areInstructionsLoading: boolean;
  className?: string;
  onSaveAllVersions: () => void;
  onTryPromptClick: () => void;
  onStopAllRuns: () => void;
};

export function RunAgentsButton(props: Props) {
  const {
    showSaveAllVersions,
    areTasksRunning,
    inputLoading,
    areInstructionsLoading,
    className,
    onSaveAllVersions,
    onTryPromptClick,
    onStopAllRuns,
  } = props;

  const [isHovering, setIsHovering] = useState(false);

  const isSaveButtonDisabled = inputLoading || areInstructionsLoading;

  if (showSaveAllVersions) {
    return (
      <SimpleTooltip content={'Save all as new versions'}>
        <Button
          variant='newDesignIndigo'
          icon={<Save16Filled />}
          loading={areTasksRunning}
          disabled={isSaveButtonDisabled}
          onClick={onSaveAllVersions}
          className={cn('min-h-8', className)}
        >
          Save All Versions
        </Button>
      </SimpleTooltip>
    );
  }

  const isNormalButtonDisabled = inputLoading || areInstructionsLoading;

  const normalButtonContent = (
    <SimpleTooltip content={isNormalButtonDisabled ? undefined : '⌘ + Enter to run'}>
      <Button
        variant='newDesignIndigo'
        icon={<Play16Filled />}
        loading={areTasksRunning}
        disabled={isNormalButtonDisabled}
        onClick={onTryPromptClick}
        className={cn('min-h-8', className)}
      >
        Run
      </Button>
    </SimpleTooltip>
  );

  const stopButtonContent = (
    <Button
      variant='newDesignIndigo'
      icon={<Stop16Filled />}
      onClick={onStopAllRuns}
      className={cn('min-h-8', className)}
    >
      Stop All Runs
    </Button>
  );

  return (
    <div onMouseEnter={() => setIsHovering(true)} onMouseLeave={() => setIsHovering(false)} className={className}>
      {isHovering && areTasksRunning ? stopButtonContent : normalButtonContent}
    </div>
  );
}
