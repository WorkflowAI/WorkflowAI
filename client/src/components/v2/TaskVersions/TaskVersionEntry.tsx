import { cx } from 'class-variance-authority';
import { FileText } from 'lucide-react';
import { useCallback, useMemo } from 'react';
import { TaskRunEnvironments } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/runs/taskRunTable/TaskRunEnvironments';
import { ResoningBadge } from '@/components/ProxyModelsCombobox/entry/ResoningBadge';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { SimpleRadioIndicator } from '@/components/ui/RadioGroup';
import { TaskEnvironmentBadge } from '@/components/v2/TaskEnvironmentBadge';
import { cn } from '@/lib/utils';
import { User } from '@/types/user';
import { VersionV1 } from '@/types/workflowAI';
import { TaskCostBadge, TaskCostView } from '../TaskCostBadge';
import { TaskRunCountButton } from '../TaskRunCountBadge/TaskRunCountBadge';
import { useViewRuns } from '../TaskRunCountBadge/useViewRuns';
import { TaskTemperatureView } from '../TaskTemperatureBadge';
import { TaskVersionTooltip } from './TaskVersionTooltip';
import { COLUMN_WIDTHS, ColumnName, SMALL_COLUMN_WIDTHS } from './TaskVersionsHeader';
import { TaskVersionAvatar } from './VersionAvatarType';
import { VersionAvatarType } from './utils';

type TaskVersionEntryProps = {
  avatarType: VersionAvatarType;
  usersByID: Record<string, User>;
  isSelected: boolean;
  onClone: () => void;
  onDeploy: () => void;
  onSelect?: (iteration: string) => void;
  onTryInPlayground: () => void;
  onViewCode: () => void;
  showGroupActions: boolean;
  version: VersionV1;
  smallMode: boolean;
  isInDemoMode: boolean;
};

export function TaskVersionEntry(props: TaskVersionEntryProps) {
  const {
    avatarType,
    usersByID,
    isSelected,
    onClone,
    onDeploy,
    onSelect,
    onTryInPlayground,
    onViewCode,
    showGroupActions,
    version,
    smallMode,
    isInDemoMode,
  } = props;
  const iteration = version.iteration;

  const handleSelect = useCallback(() => {
    onSelect?.(iteration.toString());
  }, [onSelect, iteration]);

  const onViewRuns = useViewRuns(version.schema_id, version);

  const environments = useMemo(
    () => version.deployments?.map((deployment) => deployment.environment),
    [version.deployments]
  );

  if (smallMode) {
    return (
      <TaskVersionTooltip
        onClone={onClone}
        onTryInPlayground={onTryInPlayground}
        onViewCode={onViewCode}
        onDeploy={onDeploy}
        showGroupActions={showGroupActions}
        isInDemoMode={isInDemoMode}
      >
        <div
          className={cx(
            'px-2 py-2.5 flex items-center gap-4 rounded-[2px] w-full border-b border-gray-100 last:border-transparent hover:bg-gray-100',
            !!onSelect && 'cursor-pointer'
          )}
          onClick={!!onSelect ? handleSelect : undefined}
        >
          <div className={cn('flex items-center', SMALL_COLUMN_WIDTHS[ColumnName.Version])}>
            <div className='flex items-center gap-1'>
              {!!onSelect && <SimpleRadioIndicator isSelected={isSelected} onClick={handleSelect} />}
              <TaskVersionBadgeContainer version={version} side='right' showActiveIndicator={true} height={26} />
            </div>
          </div>
          <div className='flex items-center overflow-hidden truncate gap-1.5 flex-1'>
            {!!environments && <TaskRunEnvironments environments={environments} />}
            {!!version.model && (
              <div className='flex flex-row items-center gap-1 overflow-hidden'>
                <div className='truncate text-gray-700 text-[13px] font-normal'>{version.model}</div>
                <ResoningBadge reasoning={'medium'} allowTooltips={true} />
              </div>
            )}
          </div>
          <div className={cn('flex items-center', SMALL_COLUMN_WIDTHS[ColumnName.Price])}>
            <TaskCostBadge cost={version.cost_estimate_usd} className='text-gray-500 bg-gray-50' />
          </div>
        </div>
      </TaskVersionTooltip>
    );
  }

  return (
    <TaskVersionTooltip
      onClone={onClone}
      onTryInPlayground={onTryInPlayground}
      onViewCode={onViewCode}
      onDeploy={onDeploy}
      showGroupActions={showGroupActions}
      isInDemoMode={isInDemoMode}
    >
      <div
        className={cx(
          'px-2 py-2.5 flex items-center gap-4 rounded-[2px] w-full border-b border-gray-100 last:border-transparent hover:bg-gray-50',
          !!onSelect && 'cursor-pointer'
        )}
        onClick={!!onSelect ? handleSelect : undefined}
      >
        <div className={cn('flex items-center', COLUMN_WIDTHS[ColumnName.Version])}>
          <div className='flex items-center gap-1'>
            {!!onSelect && <SimpleRadioIndicator isSelected={isSelected} onClick={handleSelect} />}
            <TaskVersionBadgeContainer version={version} side='right' showActiveIndicator={true} height={26} />
          </div>
        </div>
        <div className={cn('flex items-center overflow-hidden truncate gap-1.5', COLUMN_WIDTHS[ColumnName.Model])}>
          {!!version.model && <div className='truncate text-gray-500 text-[13px] font-normal'>{version.model}</div>}
        </div>
        <div className={cn('flex items-center', COLUMN_WIDTHS[ColumnName.Price])}>
          <TaskCostView cost={version.cost_estimate_usd} />
        </div>
        <div className={cn('flex items-center', COLUMN_WIDTHS[ColumnName.Avatar])}>
          <TaskVersionAvatar avatarType={avatarType} version={version} usersByID={usersByID} />
        </div>
        {!!environments && (
          <div className='flex flex-row gap-1'>
            {environments.map((environment) => (
              <TaskEnvironmentBadge key={environment} environment={environment} />
            ))}
          </div>
        )}
        <div className='flex-1 font-normal text-gray-700 text-[13px]'>
          {!!version.notes ? (
            <div className='flex items-center gap-1'>
              <FileText size={16} className='shrink-0' />
              <div className='line-clamp-1 break-all'>{version.notes}</div>
            </div>
          ) : (
            <div className='line-clamp-1 break-all'>{version.properties.instructions || ''}</div>
          )}
        </div>
        <div className={cn('flex items-center', COLUMN_WIDTHS[ColumnName.Temperature])}>
          <TaskTemperatureView temperature={version.properties.temperature} />
        </div>
        <div className={cn('flex items-center', COLUMN_WIDTHS[ColumnName.Runs])}>
          <TaskRunCountButton
            onClick={!!onSelect ? undefined : onViewRuns}
            runsCount={version.run_count ?? undefined}
          />
        </div>
      </div>
    </TaskVersionTooltip>
  );
}
