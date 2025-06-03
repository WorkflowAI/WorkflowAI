import { ChevronsUpDown } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { ModelBadge } from '@/components/ModelBadge/ModelBadge';
import { TaskEnvironmentBadge } from '@/components/TaskEnvironmentBadge';
import { HoverTaskVersionDetails } from '@/components/TaskIterationBadge/HoverTaskVersionDetails';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { CustomCommandInput } from '@/components/ui/Command';
import { HoverCard, HoverCardTrigger } from '@/components/ui/HoverCard';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/Popover';
import { cn } from '@/lib/utils';
import { formatSemverVersion, sortVersions } from '@/lib/versionUtils';
import { VersionsPerEnvironment } from '@/store/versions';
import { VersionEnvironment, VersionV1 } from '@/types/workflowAI';
import { TaskRunEnvironments } from '../runs/taskRunTable/TaskRunEnvironments';

type VersionPopoverItemProps = {
  environment?: VersionEnvironment;
  showFullEnvironmentName: boolean;
  version?: VersionV1;
  onClick?: () => void;
  className?: string;
};

function VersionPopoverItem(props: VersionPopoverItemProps) {
  const { environment, version, onClick, className, showFullEnvironmentName } = props;

  if (!environment && !version) {
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
          {environment && showFullEnvironmentName && <TaskEnvironmentBadge environment={environment} />}
          {environment && !showFullEnvironmentName && <TaskRunEnvironments environments={[environment]} />}
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
      {!!version && <HoverTaskVersionDetails versionId={version.id} side='right' />}
    </HoverCard>
  );
}

type VersionPopoverProps = {
  versions: VersionV1[];
  versionsPerEnvironment: VersionsPerEnvironment | undefined;
  selectedVersionId: string | undefined;
  setSelectedVersionId: (newVersionId: string | undefined) => void;
  selectedEnvironment: VersionEnvironment | undefined;
  setSelectedEnvironment: (environment: VersionEnvironment | undefined, versionId: string | undefined) => void;
};

export function VersionPopover(props: VersionPopoverProps) {
  const {
    versions,
    versionsPerEnvironment,
    selectedVersionId,
    setSelectedVersionId,
    selectedEnvironment,
    setSelectedEnvironment,
  } = props;

  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const searchLower = search.toLowerCase();

  const environmentsAndVersions = useMemo(() => {
    const sortedEnvironments: VersionEnvironment[] = ['production', 'staging', 'dev'];

    const result: { environment: VersionEnvironment; version: VersionV1 }[] = [];

    sortedEnvironments.forEach((environment) => {
      const versions = versionsPerEnvironment?.[environment];
      if (!!versions && environment.toLowerCase().includes(searchLower)) {
        const sortedVersions = sortVersions(versions);

        sortedVersions.forEach((version) => {
          result.push({
            environment,
            version,
          });
        });
      }
    });

    return result;
  }, [versionsPerEnvironment, searchLower]);

  const filteredVersions = useMemo(() => {
    return versions.filter((version) => {
      const textBadge = formatSemverVersion(version);
      return textBadge?.includes(searchLower);
    });
  }, [versions, searchLower]);

  const selectedVersion = useMemo(() => {
    return versions.find((version) => version.id === selectedVersionId);
  }, [versions, selectedVersionId]);

  const onSelectedEnvironment = useCallback(
    (environment: VersionEnvironment | undefined, versionId: string | undefined) => {
      setSelectedEnvironment(environment, versionId);
      setOpen(false);
    },
    [setSelectedEnvironment, setOpen]
  );

  const onSelectedVersionId = useCallback(
    (versionId: string | undefined) => {
      setSelectedVersionId(versionId);
      setOpen(false);
    },
    [setSelectedVersionId, setOpen]
  );

  const showTriggerVersionItem = !!selectedEnvironment || !!selectedVersionId;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div className='flex flex-row items-center gap-2 w-full border border-gray-300 bg-white rounded-[2px] min-h-10 px-3 shadow-sm cursor-pointer hover:bg-gray-100'>
          <div className='flex-1 min-w-0'>
            {showTriggerVersionItem ? (
              <VersionPopoverItem
                environment={selectedEnvironment}
                version={selectedVersion}
                className='px-0'
                showFullEnvironmentName={false}
              />
            ) : (
              <div className='text-[12px] font-medium text-gray-500 truncate'>Select</div>
            )}
          </div>
          <ChevronsUpDown className='h-4 w-4 shrink-0 text-gray-500' />
        </div>
      </PopoverTrigger>
      <PopoverContent className='w-[275px] overflow-auto max-h-[300px] p-0 rounded-[2px]'>
        <CustomCommandInput placeholder='Search versions' search={search} onSearchChange={setSearch} />
        <div className='p-1'>
          {environmentsAndVersions.length === 0 && filteredVersions.length === 0 && (
            <div className='text-sm text-center p-2'>No versions found</div>
          )}
          {environmentsAndVersions.map(({ environment, version }) => {
            return (
              <VersionPopoverItem
                key={`${environment}-${version.id}`}
                environment={environment}
                version={version}
                onClick={() => onSelectedEnvironment(environment, version.id)}
                showFullEnvironmentName={false}
              />
            );
          })}
          {filteredVersions.map((version) => {
            return (
              <VersionPopoverItem
                key={version.id}
                version={version}
                onClick={() => onSelectedVersionId(version.id)}
                showFullEnvironmentName={false}
              />
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
