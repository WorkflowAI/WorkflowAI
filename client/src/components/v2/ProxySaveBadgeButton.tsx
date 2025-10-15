import { Save16Regular } from '@fluentui/react-icons';
import Image from 'next/image';
import { DebouncedState } from 'usehooks-ts';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { isVersionSaved } from '@/lib/versionUtils';
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
  tenant: TenantID | undefined;
  taskId: TaskID;
  handleUpdateNotes?: DebouncedState<(versionId: string, notes: string) => Promise<void>> | undefined;
  onSave: () => void;
  onSendToCursor?: () => void;
  setVersionIdForCode?: (versionId: string | undefined) => void;
  showLabels?: boolean;
  tallButtons?: boolean;
};

export function ProxySaveBadgeButton(props: ProxySaveBadgeButtonProps) {
  const {
    version,
    handleUpdateNotes,
    onSave,
    onSendToCursor,
    tenant,
    taskId,
    setVersionIdForCode,
    showLabels = true,
    tallButtons = false,
  } = props;

  const isSaving = useIsSavingVersion(version?.id);
  const { isInDemoMode } = useDemoMode();
  const isSaved = isVersionSaved(version);

  return (
    <div className='flex items-center'>
      {onSendToCursor && (
        <SimpleTooltip content='Send to Cursor' tooltipDelay={100}>
          <Button
            variant='newDesign'
            size='sm'
            onClick={onSendToCursor}
            disabled={isInDemoMode}
            className='rounded-l-[2px] border-r-0 rounded-r-none shadow-none'
            style={{
              height: tallButtons ? '38px' : '28px',
            }}
          >
            <div className='flex items-center justify-center w-[16px] h-[32px]'>
              <Image
                src={'https://workflowai.blob.core.windows.net/workflowai-public/CursorMCPIcon.png'}
                alt='Cursor Icon'
                className='flex items-center justify-center w-[14px] h-[14px]'
                width={32}
                height={32}
              />
            </div>
          </Button>
        </SimpleTooltip>
      )}
      {!isSaved && (
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
            className='rounded-l-[2px] border-r-0 rounded-r-none shadow-none'
            style={{
              height: tallButtons ? '38px' : '28px',
            }}
          >
            {showLabels ? 'Save' : undefined}
          </Button>
        </SimpleTooltip>
      )}

      <div className='border-l border-gray-200'>
        <ProxyDeployBadgeButton
          isInDemoMode={isInDemoMode}
          version={version}
          tenant={tenant}
          taskId={taskId}
          showLabels={showLabels}
          tallButtons={tallButtons}
        />
      </div>
    </div>
  );
}
