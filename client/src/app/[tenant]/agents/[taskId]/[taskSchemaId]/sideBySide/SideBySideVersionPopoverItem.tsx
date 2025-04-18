import { useMemo } from 'react';
import { ModelBadge } from '@/components/ModelBadge/ModelBadge';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/HoverCard';
import { TaskVersionDetails } from '@/components/v2/TaskVersionDetails';
import { cn } from '@/lib/utils';
import { environmentsForVersion } from '@/lib/versionUtils';
import { VersionV1 } from '@/types/workflowAI';
import { TaskRunEnvironments } from '../runs/taskRunTable/TaskRunEnvironments';

type SideBySideVersionPopoverItemProps = {
  version?: VersionV1;
  onClick?: () => void;
  className?: string;
  showDetails?: boolean;
};

export function SideBySideVersionPopoverItem(props: SideBySideVersionPopoverItemProps) {
  const { version, onClick, className, showDetails = true } = props;

  const environments = useMemo(() => {
    return environmentsForVersion(version);
  }, [version]);

  if (!version) {
    return null;
  }

  return (
    <HoverCard>
      <HoverCardTrigger>
        <div
          className={cn(
            'flex flex-row items-center gap-1 rounded-[1px] hover:bg-gray-100 cursor-pointer px-2 py-1 overflow-hidden',
            className
          )}
          onClick={onClick}
        >
          {!!environments && environments.length > 0 && <TaskRunEnvironments environments={environments} />}
          {version && (
            <>
              <TaskVersionBadgeContainer
                version={version}
                showDetails={false}
                showNotes={false}
                showHoverState={false}
                showSchema={true}
                interaction={false}
                showFavorite={false}
              />
              <ModelBadge version={version} className='ml-1' />
            </>
          )}
        </div>
      </HoverCardTrigger>
      {!!version && showDetails && (
        <HoverCardContent className='w-fit max-w-[660px] p-0 rounded-[2px] border-gray-200' side='right'>
          <TaskVersionDetails version={version} className='w-[350px]' />
        </HoverCardContent>
      )}
    </HoverCard>
  );
}
