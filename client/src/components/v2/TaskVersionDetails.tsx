import { cx } from 'class-variance-authority';
import { useCallback, useMemo } from 'react';
import { DebouncedState } from 'usehooks-ts';
import { ProxyMessagesView } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/proxy-messages/ProxyMessagesView';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { TaskVersionNotes } from '@/components/TaskVersionNotes';
import { Badge } from '@/components/ui/Badge';
import { TaskRunCountBadge } from '@/components/v2/TaskRunCountBadge/TaskRunCountBadge';
import { environmentsForVersion } from '@/lib/versionUtils';
import { ProxyMessage, VersionV1 } from '@/types/workflowAI';
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
        <div className='text-[13px] font-medium text-gray-800 capitalize'>{title}</div>
        <div className='flex-1 flex justify-start overflow-hidden'>
          <div className='truncate'>{children}</div>
        </div>
      </div>
      {footer}
    </div>
  );
}

const keysToFilter = [
  'model',
  'provider',
  'temperature',
  'examples',
  'few_shot',
  'instructions',
  'runner_name',
  'runner_version',
  'task_schema_id',
  'task_variant_id',
  'template_name',
  'model_name',
  'model_icon',
  'messages',
  'is_chain_of_thought_enabled',
];

function extractNamesAndValues(version: VersionV1 | undefined): { name: string; value: string }[] {
  if (!version) {
    return [];
  }

  const keys = Object.keys(version.properties).filter((key) => !keysToFilter.includes(key));

  const result: { name: string; value: string }[] = [];

  keys.forEach((key) => {
    const value = String(version.properties[key]);
    if (!!value && value !== 'null') {
      result.push({ name: key, value });
    }
  });

  return result;
}

type TaskMetadataProps = {
  bottomText?: string;
  children?: React.ReactNode;
  className?: string;
  handleUpdateNotes?: DebouncedState<(versionId: string, notes: string) => Promise<void>>;
  limitNumberOfLines?: boolean;
  maximalHeightOfInstructions?: number;
  version: VersionV1;
};

export function TaskVersionDetails(props: TaskMetadataProps) {
  const {
    bottomText,
    children,
    className,
    handleUpdateNotes,
    limitNumberOfLines = false,
    maximalHeightOfInstructions = 173,
    version,
  } = props;
  const versionId = version?.id;
  const properties = version?.properties;

  const onViewRuns = useViewRuns(version?.schema_id, version);

  const environments = useMemo(() => environmentsForVersion(version) || [], [version]);

  const { temperature, instructions, provider, few_shot, messages } = properties;
  const model = version?.model;

  const namesAndValues: { name: string; value: string }[] = useMemo(() => extractNamesAndValues(version), [version]);

  const onUpdateNotes = useCallback(
    async (notes: string) => {
      if (!versionId || !handleUpdateNotes) return;
      await handleUpdateNotes(versionId, notes);
    },
    [versionId, handleUpdateNotes]
  );

  if (!version || !properties) {
    return null;
  }

  const fewShotCount = few_shot?.count;

  const runCount = version.run_count ?? undefined;

  return (
    <div className={cx(className, 'pb-1.5 bg-white')}>
      {versionId !== undefined && (
        <TaskMetadataSection
          title='version'
          footer={
            <TaskVersionNotes
              notes={version.notes}
              onUpdateNotes={!!handleUpdateNotes ? onUpdateNotes : undefined}
              versionId={versionId}
            />
          }
        >
          <TaskVersionBadgeContainer version={version} showDetails={false} />
        </TaskMetadataSection>
      )}

      {'cost_estimate_usd' in version && (
        <TaskMetadataSection title='cost (per 1k runs)'>
          <TaskCostBadge cost={version.cost_estimate_usd} />
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
          <TaskModelBadge model={model} providerId={provider} />
        </TaskMetadataSection>
      )}

      {namesAndValues.map(({ name, value }) => (
        <TaskMetadataSection key={name} title={name}>
          <Badge variant='tertiary' className='w-fit'>
            {value}
          </Badge>
        </TaskMetadataSection>
      ))}

      {fewShotCount !== undefined && fewShotCount !== null && (
        <TaskMetadataSection title='few-shot'>
          {`${fewShotCount} ${fewShotCount > 1 ? 'examples' : 'example'}`}
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
          <ProxyMessagesView messages={messages as ProxyMessage[]} />
        </div>
      )}

      {temperature !== undefined && temperature !== null && (
        <TaskMetadataSection title='temperature'>
          <TaskTemperatureBadge temperature={temperature} />
        </TaskMetadataSection>
      )}

      <TaskMetadataSection title='runs'>
        <TaskRunCountBadge runsCount={runCount} onClick={onViewRuns} />
      </TaskMetadataSection>

      {children}
    </div>
  );
}
