import { Checkmark20Regular, Play20Regular, Stop20Regular } from '@fluentui/react-icons';
import { useCallback, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { ProxySaveBadgeButton } from '@/components/v2/ProxySaveBadgeButton';
import { useIsAllowed } from '@/lib/hooks/useIsAllowed';
import { useVersions } from '@/store/versions';
import { TaskID, TenantID } from '@/types/aliases';
import { VersionV1 } from '@/types/workflowAI';
import { TaskRunner } from '../../playground/hooks/useTaskRunners';

type Props = {
  taskRunner: TaskRunner;
  disabled: boolean;
  containsError: boolean;
  version: VersionV1 | undefined;
  tenant: TenantID | undefined;
  taskId: TaskID;
};
export function ProxyRunButton(props: Props) {
  const { taskRunner, disabled, containsError, version, tenant, taskId } = props;

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

  const saveVersion = useVersions((state) => state.saveVersion);
  const { checkIfSignedIn } = useIsAllowed();

  const onSave = useCallback(async () => {
    if (!checkIfSignedIn() || !version) {
      return;
    }
    await saveVersion(tenant, taskId, version.id);
  }, [saveVersion, tenant, taskId, version, checkIfSignedIn]);

  if (!taskRunner.loading && !!version) {
    return (
      <div className='flex items-center justify-center shadow-sm'>
        <ProxySaveBadgeButton
          version={version}
          onSave={onSave}
          tenant={tenant}
          taskId={taskId}
          showLabels={false}
          tallButtons={true}
        />
      </div>
    );
  }

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
