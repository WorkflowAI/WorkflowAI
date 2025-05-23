import { Save16Regular } from '@fluentui/react-icons';
import { HoverCard, HoverCardContentProps, HoverCardTrigger } from '@radix-ui/react-hover-card';
import { useCallback, useMemo, useState } from 'react';
import { checkVersionForProxy } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/proxy/hooks/useIsProxy';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useFavoriteToggle } from '@/lib/hooks/useFavoriteToggle';
import { useIsAllowed } from '@/lib/hooks/useIsAllowed';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { useUpdateNotes } from '@/lib/hooks/useUpdateNotes';
import { cn } from '@/lib/utils';
import { formatSemverVersion, isVersionSaved } from '@/lib/versionUtils';
import { useIsSavingVersion } from '@/store/fetchers';
import { useVersions } from '@/store/versions';
import { TaskSchemaID } from '@/types/aliases';
import { VersionV1 } from '@/types/workflowAI';
import { Button } from '../ui/Button';
import { SimpleTooltip } from '../ui/Tooltip';
import { ProxyDeployBadgeButton } from '../v2/ProxyDeployBadgeButton';
import { ProxySaveBadgeButton } from '../v2/ProxySaveBadgeButton';
import { AddNoteCard } from './AddNoteCard';
import { HoverTaskVersionDetails } from './HoverTaskVersionDetails';
import { TaskStats } from './TaskIterationStats';
import { TaskIterationActivityIndicator } from './TaskRunsActivityIndicator';
import { TaskVersionBadgeContent } from './TaskVersionBadgeContent';

type TaskVersionBadgeContainerProps = {
  version: VersionV1;

  showDetails?: boolean;
  showNotes?: boolean;
  showHoverState?: boolean;
  showActiveIndicator?: boolean;
  showSchema?: boolean;
  showFavorite?: boolean;
  interaction?: boolean;
  hideMinorVersion?: boolean;

  side?: HoverCardContentProps['side'];
  align?: HoverCardContentProps['align'];

  className?: string;
  height?: number;
};

export function TaskVersionBadgeContainer(props: TaskVersionBadgeContainerProps) {
  const {
    version,
    showHoverState = true,
    showDetails = true,
    showNotes = true,
    showActiveIndicator = false,
    showSchema = false,
    showFavorite = true,
    side,
    align,
    className,
    height,
    interaction = true,
    hideMinorVersion = false,
  } = props;
  const [noteHoverCardOpen, setNoteHoverCardOpen] = useState(false);

  const badgeText = formatSemverVersion(version, hideMinorVersion);
  const isFavorite = version.is_favorite === true;

  const { tenant, taskId } = useTaskSchemaParams();

  const taskSchemaId = `${version.schema_id}` as TaskSchemaID;

  const isProxy = useMemo(() => {
    return checkVersionForProxy(version);
  }, [version]);

  const { handleUpdateNotes } = useUpdateNotes({
    tenant: tenant,
    taskId: taskId,
  });

  const { handleFavoriteToggle } = useFavoriteToggle({
    tenant: tenant,
    taskId: taskId,
  });

  const { isInDemoMode } = useDemoMode();

  const onFavoriteToggle = useCallback(
    (event: React.MouseEvent) => {
      if (version === undefined || isInDemoMode || !showFavorite) return;

      event.stopPropagation();
      const newIsFavorite = !version?.is_favorite;
      if (newIsFavorite) {
        setNoteHoverCardOpen(true);
      }
      handleFavoriteToggle(version);
    },
    [handleFavoriteToggle, version, showFavorite, isInDemoMode]
  );

  const saveVersion = useVersions((state) => state.saveVersion);
  const { checkIfSignedIn } = useIsAllowed();

  const onSave = useCallback(async () => {
    if (!checkIfSignedIn()) {
      return;
    }
    await saveVersion(tenant, taskId, version.id);
  }, [saveVersion, tenant, taskId, version.id, checkIfSignedIn]);

  const isActive = useMemo(() => {
    if (!version?.last_active_at) return false;

    const lastActiveDate = new Date(version.last_active_at);
    const fortyEightHoursAgo = new Date(Date.now() - 48 * 60 * 60 * 1000);

    return lastActiveDate >= fortyEightHoursAgo;
  }, [version?.last_active_at]);

  const shouldShowActiveIndicator = showActiveIndicator && isActive && version.id !== undefined;

  const isSaving = useIsSavingVersion(version?.id);
  const isSaved = isVersionSaved(version);

  if (!isSaved) {
    if (isProxy) {
      return (
        <ProxySaveBadgeButton
          version={version}
          onSave={onSave}
          handleUpdateNotes={handleUpdateNotes}
          tenant={tenant}
          taskId={taskId}
        />
      );
    } else {
      return (
        <SimpleTooltip content={'Save as a new version'}>
          <Button
            variant='newDesign'
            size='sm'
            icon={<Save16Regular />}
            onClick={onSave}
            loading={isSaving}
            disabled={isInDemoMode}
          >
            Save
          </Button>
        </SimpleTooltip>
      );
    }
  }

  if (!interaction) {
    return (
      <TaskVersionBadgeContent
        text={badgeText}
        schemaText={showSchema ? taskSchemaId : undefined}
        isFavorite={isFavorite}
        onFavoriteToggle={onFavoriteToggle}
        showFavorite={showFavorite}
        className={className}
        showHoverState={showHoverState}
        openRightSide={shouldShowActiveIndicator}
        height={height}
      />
    );
  }

  return (
    <div className={cn('flex flex-row items-center', !!height && `h-[${height}px]`)}>
      <HoverCard
        open={noteHoverCardOpen || undefined}
        key={noteHoverCardOpen ? 'open' : 'closed'}
        openDelay={300}
        onOpenChange={(open) => {
          const tooltips = document.querySelectorAll('[data-radix-popper-content-wrapper]');

          tooltips.forEach((tooltip) => {
            if (tooltip instanceof HTMLElement) {
              tooltip.style.display = open ? 'none' : 'block';
            }
          });
        }}
      >
        <div className='flex flex-row items-center'>
          <HoverCardTrigger asChild>
            <div>
              <TaskVersionBadgeContent
                text={badgeText}
                schemaText={showSchema ? taskSchemaId : undefined}
                isFavorite={isFavorite}
                onFavoriteToggle={onFavoriteToggle}
                showFavorite={showFavorite}
                className={cn(className, isProxy && 'h-7')}
                showHoverState={showHoverState}
                openRightSide={shouldShowActiveIndicator}
                height={height}
              />
            </div>
          </HoverCardTrigger>
          {isProxy && (
            <ProxyDeployBadgeButton isInDemoMode={isInDemoMode} version={version} tenant={tenant} taskId={taskId} />
          )}
        </div>
        {showDetails && !noteHoverCardOpen && (
          <HoverTaskVersionDetails
            side={side}
            align={align}
            version={version}
            handleUpdateNotes={handleUpdateNotes}
            isProxy={isProxy}
          />
        )}
        {showNotes && noteHoverCardOpen && (
          <AddNoteCard
            versionId={version.id}
            notes={version?.notes}
            handleUpdateNotes={handleUpdateNotes}
            closeNoteHoverCard={() => setNoteHoverCardOpen(false)}
          />
        )}
      </HoverCard>
      {shouldShowActiveIndicator && (
        <SimpleTooltip
          content={<TaskStats tenant={tenant} taskSchemaId={taskSchemaId} taskId={taskId} versionID={version?.id} />}
          side='top'
        >
          <div>
            <TaskIterationActivityIndicator height={height} />
          </div>
        </SimpleTooltip>
      )}
    </div>
  );
}
