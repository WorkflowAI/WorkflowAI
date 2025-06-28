import { useMemo } from 'react';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { TASK_RUN_ID_PARAM } from '@/lib/constants';
import { formatDateTime, formatRelativeTime } from '@/lib/formatters/timeFormatter';
import { useRedirectWithParams } from '@/lib/queryString';
import { environmentsForVersion } from '@/lib/versionUtils';
import { RunItemV1, VersionV1 } from '@/types/workflowAI';
import { TaskRunReview } from '../TaskRunReview';
import { TaskRunEnvironments } from './TaskRunEnvironments';
import { TaskRunHoverableInputOutput } from './TaskRunHoverableInputOutput';

type TaskRunTableRowProps = {
  runItem: RunItemV1;
  version: VersionV1 | undefined;
  redirectWithParams: ReturnType<typeof useRedirectWithParams>;
};

export function TaskRunTableRow(props: TaskRunTableRowProps) {
  const { runItem, version, redirectWithParams } = props;

  const environments = useMemo(() => {
    return environmentsForVersion(version);
  }, [version]);

  return (
    <div
      className='flex flex-row w-full border-b last:border-b-0 border-gray-200/60 text-[13px] text-gray-700 items-center cursor-pointer'
      onClick={() => {
        redirectWithParams({
          params: { [TASK_RUN_ID_PARAM]: runItem.id },
        });
      }}
    >
      <div className='flex-1 overflow-hidden max-w-full cursor-pointer'>
        <TaskRunHoverableInputOutput runItem={runItem} />
      </div>
      <div className='w-[60px]'>
        <div className='w-fit flex text-ellipsis whitespace-nowrap h-full items-center justify-center text-gray-700 text-[12px] font-medium rounded-[2px] bg-gray-200 px-1.5 py-[3px]'>
          #{runItem.task_schema_id ?? 0}
        </div>
      </div>
      <div className='flex flex-row gap-[6px] items-center justify-start w-[140px]'>
        {!!version ? (
          <TaskVersionBadgeContainer version={version} side='left' showActiveIndicator={true} height={26} />
        ) : (
          <SimpleTooltip
            content={
              'To save this version, open the run details by\ntapping the row and tap Save in the\nVersion section'
            }
            tooltipClassName='whitespace-pre-line text-center'
            tooltipDelay={100}
          >
            <div className='w-fit flex text-ellipsis whitespace-nowrap h-full items-center justify-center text-gray-700 text-[13px] font-medium rounded-[2px] bg-white border border-gray-200 border-dashed px-1.5 py-[3px]'>
              (not saved)
            </div>
          </SimpleTooltip>
        )}
        {!!environments && environments.length > 0 && <TaskRunEnvironments environments={environments} />}
      </div>
      <SimpleTooltip
        content={formatDateTime(runItem.created_at)}
        tooltipClassName='whitespace-pre-line text-center'
        tooltipDelay={100}
      >
        <div className='w-[64px] text-gray-500 text-[13px] font-normal'>{formatRelativeTime(runItem.created_at)}</div>
      </SimpleTooltip>
      <div className='w-[60px]'>
        <TaskRunReview taskRun={runItem} />
      </div>
    </div>
  );
}
