import { ModelBadge } from '@/components/ModelBadge/ModelBadge';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { TaskCostBadge } from '@/components/v2/TaskCostBadge';
import { cn } from '@/lib/utils';
import { ModelResponse, VersionV1 } from '@/types/workflowAI';

type SideBySideVersionPopoverModelItemProps = {
  model?: ModelResponse;
  onClick?: () => void;
  className?: string;
  baseVersion?: VersionV1;
  hidePrice?: boolean;
};

export function SideBySideVersionPopoverModelItem(props: SideBySideVersionPopoverModelItemProps) {
  const { model, onClick, className, baseVersion, hidePrice = false } = props;

  if (!model) {
    return null;
  }

  return (
    <div
      className={cn(
        'flex flex-row items-center gap-1 rounded-[1px] hover:bg-gray-100 cursor-pointer py-1 overflow-hidden',
        className
      )}
      onClick={onClick}
    >
      {model && (
        <div className='flex flex-row items-center justify-between gap-2 w-full pr-2'>
          <div className='flex flex-row items-center gap-2'>
            {baseVersion && (
              <TaskVersionBadgeContainer
                version={baseVersion}
                showDetails={false}
                showNotes={false}
                showHoverState={false}
                showSchema={true}
                interaction={false}
                showFavorite={false}
                hideMinorVersion={true}
              />
            )}
            <ModelBadge model={model} />
          </div>

          {!hidePrice && (
            <TaskCostBadge
              cost={model.average_cost_per_run_usd}
              className=' border-gray-200 bg-gray-50 rounded-[2px] text-gray-500 text-[13px] font-medium py-0 px-[5px]'
              supportTooltip={true}
            />
          )}
        </div>
      )}
    </div>
  );
}
