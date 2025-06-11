import { Save16Regular } from '@fluentui/react-icons';
import { DebouncedState } from 'usehooks-ts';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useIsSavingVersion } from '@/store/fetchers';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { VersionV1 } from '@/types/workflowAI';
import { Button } from '../ui/Button';
import { SimpleTooltip } from '../ui/Tooltip';
import { ProxyDeployBadgeButton } from './ProxyDeployBadgeButton';
import { ProxyVersionDetails } from './ProxyVersionDetails';

type ProxySaveBadgeButtonProps = {
  version: VersionV1;
  tenant: TenantID;
  taskId: TaskID;
  handleUpdateNotes?: DebouncedState<(versionId: string, notes: string) => Promise<void>> | undefined;
  onSave: () => void;
  setVersionIdForCode?: (versionId: string | undefined) => void;
};

export function ProxySaveBadgeButton(props: ProxySaveBadgeButtonProps) {
  const { version, handleUpdateNotes, onSave, tenant, taskId, setVersionIdForCode } = props;

  const isSaving = useIsSavingVersion(version?.id);
  const { isInDemoMode } = useDemoMode();

  return (
    <div className='flex items-center'>
      <SimpleTooltip
        content={
          <ProxyVersionDetails
            version={version}
            handleUpdateNotes={handleUpdateNotes}
            className='w-[430px]'
            setVersionIdForCode={setVersionIdForCode}
          />
        }
        tooltipClassName='p-0 rounded-[2px] border border-gray-200'
        tooltipDelay={100}
      >
        <Button
          variant='newDesign'
          size='sm'
          icon={<Save16Regular />}
          onClick={onSave}
          loading={isSaving}
          disabled={isInDemoMode}
          className='rounded-l-[2px] rounded-r-none shadow-none'
        >
          Save
        </Button>
      </SimpleTooltip>
      <ProxyDeployBadgeButton isInDemoMode={isInDemoMode} version={version} tenant={tenant} taskId={taskId} />
    </div>
  );
}
