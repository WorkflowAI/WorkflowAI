import { ArrowCircleUp16Regular } from '@fluentui/react-icons';
import { useCallback, useMemo, useState } from 'react';
import { useIsAllowed } from '@/lib/hooks/useIsAllowed';
import { environmentsForVersion, getEnvironmentFullName, isVersionSaved } from '@/lib/versionUtils';
import { useVersions } from '@/store/versions';
import { TaskID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';
import { VersionV1 } from '@/types/workflowAI';
import { useDeployVersionModal } from '../DeployIterationModal/DeployVersionModal';
import { EnvironmentIcon } from '../icons/EnvironmentIcon';
import { Button } from '../ui/Button';
import { SimpleTooltip } from '../ui/Tooltip';

type ProxyDeployBadgeButtonProps = {
  isInDemoMode: boolean;
  version: VersionV1;
  tenant: TenantID | undefined;
  taskId: TaskID;
  showLabels?: boolean;
  tallButtons?: boolean;
};

export function ProxyDeployBadgeButton(props: ProxyDeployBadgeButtonProps) {
  const { isInDemoMode, version, tenant, taskId, showLabels = true, tallButtons = false } = props;

  const { onDeployToClick: onDeploy } = useDeployVersionModal();
  const [isOpeningDeploy, setIsOpeningDeploy] = useState(false);
  const { checkIfSignedIn } = useIsAllowed();
  const saveVersion = useVersions((state) => state.saveVersion);

  const onDeployToClick = useCallback(async () => {
    const versionId = version?.id;
    if (!tenant || !taskId || !versionId) return;

    if (!checkIfSignedIn()) {
      return;
    }

    setIsOpeningDeploy(true);
    onDeploy(versionId);

    if (!isVersionSaved(version)) {
      await saveVersion(tenant, taskId, versionId);
    }

    setIsOpeningDeploy(false);
  }, [onDeploy, version, saveVersion, tenant, taskId, checkIfSignedIn]);

  const environments = useMemo(() => {
    return environmentsForVersion(version);
  }, [version]);

  const firstEnvironment = useMemo(() => {
    return environments?.[0];
  }, [environments]);

  const tooltipContent = useMemo(() => {
    const deployedEnvironments = environments?.map((environment) => getEnvironmentFullName(environment)) || [];

    if (deployedEnvironments.length > 0) {
      const envList = deployedEnvironments.join(', ').replace(/, ([^,]*)$/, ' and $1');
      return `Currently deployed to ${envList}.\nTap to deploy to another environment.`;
    }
    return 'Deploy';
  }, [environments]);

  return (
    <SimpleTooltip
      content={tooltipContent}
      tooltipClassName='rounded-[2px] whitespace-pre-line text-center leading-5'
      tooltipDelay={100}
    >
      <Button
        variant='newDesign'
        size='none'
        icon={
          firstEnvironment ? (
            <EnvironmentIcon
              environment={firstEnvironment}
              className='w-[18px] h-[18px] bg-gray-700 text-white rounded-[2px] p-[2px]'
            />
          ) : (
            <ArrowCircleUp16Regular />
          )
        }
        onClick={onDeployToClick}
        disabled={isInDemoMode}
        className='rounded-l-none rounded-r-[2px] shadow-none border-l-0 px-2 text-[12px]'
        style={{
          height: tallButtons ? '38px' : '28px',
        }}
        loading={isOpeningDeploy}
      >
        {showLabels ? 'Deploy' : undefined}
      </Button>
    </SimpleTooltip>
  );
}
