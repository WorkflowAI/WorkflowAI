import { InfoRegular } from '@fluentui/react-icons';
import Link from 'next/link';
import { useMemo } from 'react';
import { useDeployVersionModal } from '@/components/DeployIterationModal/DeployVersionModal';
import { Button } from '@/components/ui/Button';
import { environmentsForVersion, formatSemverVersion } from '@/lib/versionUtils';
import { TaskSchemaID } from '@/types/aliases';
import { VersionV1 } from '@/types/workflowAI';

type DeployBannerProps = {
  version: VersionV1 | undefined;
};

export function DeployBanner(props: DeployBannerProps) {
  const { version } = props;

  const { onDeployToClick } = useDeployVersionModal();

  const notDeployed = useMemo(() => {
    const environments = environmentsForVersion(version);
    return environments?.length === 0 || environments === undefined;
  }, [version]);

  if (!version || !notDeployed) {
    return null;
  }

  const badgeText = formatSemverVersion(version);

  return (
    <div className='flex w-full px-4 py-3 border-b border-dashed border-gray-200'>
      <div className='flex flex-row gap-2 w-full items-center bg-indigo-50 rounded-[2px] border-indigo-200 border p-3'>
        <InfoRegular className='w-4 h-4 text-indigo-500' />
        <div className='flex flex-col flex-1 gap-[2px]'>
          <div className='text-[13px] font-semibold text-indigo-700'>
            Want to update versions without updating your code?
          </div>
          <div className='text-[13px] font-normal text-indigo-700'>
            Use deployments to point a specific version to an environment (dev, staging, prod.) Learn more{' '}
            <Link
              href='https://docs.workflowai.com/features/deployments'
              className='text-indigo-700 underline'
              target='_blank'
            >
              here
            </Link>
            .
          </div>
        </div>
        <Button
          variant='newDesignIndigo'
          onClick={() => onDeployToClick(version?.id, `${version?.schema_id}` as TaskSchemaID, true)}
        >
          Deploy Version {badgeText}
        </Button>
      </div>
    </div>
  );
}
