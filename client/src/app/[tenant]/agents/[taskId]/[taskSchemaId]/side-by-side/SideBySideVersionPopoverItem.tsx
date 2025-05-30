import { useMemo } from 'react';
import { ModelBadge } from '@/components/ModelBadge/ModelBadge';
import { HoverTaskVersionDetails } from '@/components/TaskIterationBadge/HoverTaskVersionDetails';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { HoverCard, HoverCardTrigger } from '@/components/ui/HoverCard';
import { cn } from '@/lib/utils';
import { environmentsForVersion } from '@/lib/versionUtils';
import { isVersionSaved } from '@/lib/versionUtils';
import { VersionV1 } from '@/types/workflowAI';
import { TaskRunEnvironments } from '../runs/taskRunTable/TaskRunEnvironments';

type SideBySideVersionPopoverItemProps = {
  version?: VersionV1;
  onClick?: () => void;
  className?: string;
  showDetails?: boolean;
  setVersionIdForCode?: (versionId: string | undefined) => void;
};

export function SideBySideVersionPopoverItem(props: SideBySideVersionPopoverItemProps) {
  const { version, onClick, className, showDetails = true, setVersionIdForCode } = props;

  const environments = useMemo(() => {
    return environmentsForVersion(version);
  }, [version]);

  const isSaved = useMemo(() => {
    return version ? isVersionSaved(version) : false;
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
              {isSaved && (
                <TaskVersionBadgeContainer
                  version={version}
                  showDetails={false}
                  showNotes={false}
                  showHoverState={false}
                  showSchema={true}
                  interaction={false}
                  showFavorite={false}
                  className='mr-1'
                  setVersionIdForCode={setVersionIdForCode}
                />
              )}
              <ModelBadge version={version} />
            </>
          )}
        </div>
      </HoverCardTrigger>
      {!!version && showDetails && isSaved && (
        <HoverTaskVersionDetails versionId={version.id} side='right' setVersionIdForCode={setVersionIdForCode} />
      )}
    </HoverCard>
  );
}
