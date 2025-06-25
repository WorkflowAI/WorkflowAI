import { Code16Regular } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { useRouter } from 'next/navigation';
import { useCallback, useMemo, useState } from 'react';
import { DebouncedState } from 'usehooks-ts';
import { ProxyMessagesView } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/proxy-messages/ProxyMessagesView';
import { TaskVersionNotes } from '@/components/TaskVersionNotes';
import { TaskRunCountBadge } from '@/components/v2/TaskRunCountBadge/TaskRunCountBadge';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useIsAllowed } from '@/lib/hooks/useIsAllowed';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { taskApiRoute } from '@/lib/routeFormatter';
import { environmentsForVersion, formatSemverVersion, isVersionSaved } from '@/lib/versionUtils';
import { useVersions } from '@/store/versions';
import { TaskSchemaID } from '@/types/aliases';
import { ProxyMessage, VersionV1 } from '@/types/workflowAI';
import { AdvencedSettingsDetails } from '../TaskRunModal/proxy/AdvencedSettingsDetails';
import { Button } from '../ui/Button';
import { TaskCostBadge } from './TaskCostBadge';
import { TaskEnvironmentBadge } from './TaskEnvironmentBadge';
import { TaskModelBadge } from './TaskModelBadge';
import { useViewRuns } from './TaskRunCountBadge/useViewRuns';
import { TaskTemperatureBadge } from './TaskTemperatureBadge';

type TaskMetadataSectionProps = {
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
};

export function TaskMetadataSection(props: TaskMetadataSectionProps) {
  const { title, children, footer } = props;

  return (
    <div className='flex flex-col gap-2 px-4 py-1.5 font-lato'>
      <div className='flex flex-col gap-1'>
        <div className='text-[13px] font-medium text-gray-900 capitalize'>{title}</div>
        <div className='flex-1 flex justify-start overflow-hidden'>
          <div className='truncate'>{children}</div>
        </div>
      </div>
      {footer}
    </div>
  );
}

type TaskMetadataProps = {
  bottomText?: string;
  children?: React.ReactNode;
  className?: string;
  handleUpdateNotes?: DebouncedState<(versionId: string, notes: string) => Promise<void>>;
  limitNumberOfLines?: boolean;
  maximalHeightOfInstructions?: number;
  version: VersionV1;
  setVersionIdForCode?: (versionId: string | undefined) => void;
};

export function ProxyVersionDetails(props: TaskMetadataProps) {
  const {
    bottomText,
    children,
    className,
    handleUpdateNotes,
    limitNumberOfLines = false,
    maximalHeightOfInstructions = 173,
    version,
    setVersionIdForCode,
  } = props;
  const { tenant, taskId } = useTaskSchemaParams();

  const versionId = version?.id;
  const properties = version?.properties;

  const router = useRouter();
  const onViewRuns = useViewRuns(version?.schema_id, version);

  const environments = useMemo(() => environmentsForVersion(version) || [], [version]);

  const { temperature, instructions, provider, messages } = properties;
  const model = version?.model;

  const isSaved = isVersionSaved(version);
  const { isInDemoMode } = useDemoMode();

  const versionNumber = useMemo(() => {
    if (!version) {
      return undefined;
    }
    return formatSemverVersion(version);
  }, [version]);

  const onUpdateNotes = useCallback(
    async (notes: string) => {
      if (!versionId || !handleUpdateNotes) return;
      await handleUpdateNotes(versionId, notes);
    },
    [versionId, handleUpdateNotes]
  );

  const saveVersion = useVersions((state) => state.saveVersion);
  const { checkIfSignedIn } = useIsAllowed();

  const [isOpeningCode, setIsOpeningCode] = useState(false);

  const onOpenTaskCode = useCallback(async () => {
    if (!version) {
      return;
    }

    const versionId = version.id;
    const taskSchemaId = `${version.schema_id}` as TaskSchemaID;

    if (!tenant || !taskId || !taskSchemaId || !versionId) return;

    if (!checkIfSignedIn()) {
      return;
    }

    setIsOpeningCode(true);
    if (!isVersionSaved(version)) {
      await saveVersion(tenant, taskId, versionId);
    }

    if (setVersionIdForCode) {
      setVersionIdForCode(versionId);
    } else {
      router.push(
        taskApiRoute(tenant, taskId, taskSchemaId, {
          selectedVersionId: versionId,
        })
      );
    }

    setIsOpeningCode(false);
  }, [router, tenant, taskId, version, saveVersion, checkIfSignedIn, setVersionIdForCode]);

  if (!version || !properties) {
    return null;
  }

  const runCount = version.run_count ?? undefined;

  return (
    <div className={cx(className, 'pb-1.5 bg-white')}>
      <div className='flex flex-row gap-2 items-center justify-between border-b border-gray-200 border-dashed h-11 px-4 mb-2'>
        {isSaved ? (
          <div className='text-[15px] font-semibold text-gray-700'>Version {versionNumber}</div>
        ) : (
          <div className='text-[15px] font-semibold text-gray-700'>Version Preview</div>
        )}
        <Button
          variant='newDesign'
          size='sm'
          icon={<Code16Regular />}
          onClick={onOpenTaskCode}
          loading={isOpeningCode}
          disabled={isInDemoMode}
        >
          View Code
        </Button>
      </div>

      {version.notes !== undefined && (
        <TaskMetadataSection title='Notes'>
          <TaskVersionNotes
            notes={version.notes}
            onUpdateNotes={!!handleUpdateNotes ? onUpdateNotes : undefined}
            versionId={versionId}
          />
        </TaskMetadataSection>
      )}
      {environments.length > 0 && (
        <TaskMetadataSection title='environment'>
          <div className='flex flex-wrap items-center justify-end gap-1'>
            {environments.map((environment) => (
              <TaskEnvironmentBadge key={environment} environment={environment} />
            ))}
          </div>
        </TaskMetadataSection>
      )}
      {model && (
        <TaskMetadataSection title='model'>
          <TaskModelBadge model={model} providerId={provider} reasoning={'medium'} allowTooltips={false} />
        </TaskMetadataSection>
      )}

      {!!instructions && (
        <div className='flex flex-col w-full items-top pl-4 pr-4 py-1.5 gap-1'>
          <div className='text-[13px] font-medium text-gray-800'>Instructions</div>
          <div>
            <div
              className={`flex-1 text-gray-900 bg-white px-3 py-2 border border-gray-300 rounded-[2px] overflow-auto font-lato font-normal text-[13px]`}
              style={{
                maxHeight: maximalHeightOfInstructions,
              }}
            >
              <p className={cx('whitespace-pre-line', limitNumberOfLines === true && 'line-clamp-5')}>{instructions}</p>
            </div>

            {!!bottomText && (
              <p className='flex justify-end text-slate-500 text-xs font-medium pt-3 pr-1'>{bottomText}</p>
            )}
          </div>
        </div>
      )}
      {!!messages && (
        <div className='flex flex-col w-full items-top pl-4 pr-4 py-1.5 gap-1'>
          <div className='text-[13px] font-medium text-gray-800'>Messages</div>
          <div className='flex flex-col w-full max-h-[400px] overflow-y-auto'>
            <ProxyMessagesView messages={messages as ProxyMessage[]} />
          </div>
        </div>
      )}

      <div className='grid grid-cols-3 gap-2 pb-1'>
        {temperature !== undefined && temperature !== null && (
          <TaskMetadataSection title='temperature'>
            <TaskTemperatureBadge temperature={temperature} />
          </TaskMetadataSection>
        )}

        {'cost_estimate_usd' in version && (
          <TaskMetadataSection title='cost'>
            <TaskCostBadge cost={version.cost_estimate_usd} />
          </TaskMetadataSection>
        )}

        <TaskMetadataSection title='runs'>
          <TaskRunCountBadge runsCount={runCount} onClick={onViewRuns} />
        </TaskMetadataSection>
      </div>

      <div className='flex w-full px-4'>
        <AdvencedSettingsDetails version={version} style='single' borderColor='border-gray-200' />
      </div>

      {children}
    </div>
  );
}
