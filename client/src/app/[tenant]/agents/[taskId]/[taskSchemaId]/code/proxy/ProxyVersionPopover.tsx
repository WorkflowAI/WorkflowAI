import { ChevronsUpDown } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { ModelBadge } from '@/components/ModelBadge/ModelBadge';
import { HoverTaskVersionDetails } from '@/components/TaskIterationBadge/HoverTaskVersionDetails';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { CustomCommandInput } from '@/components/ui/Command';
import { HoverCard, HoverCardTrigger } from '@/components/ui/HoverCard';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/Popover';
import { cn } from '@/lib/utils';
import {
  environmentsForVersion,
  formatSemverVersion,
  sortVersionsTakingIntoAccountEnvironments,
} from '@/lib/versionUtils';
import { VersionEnvironment, VersionV1 } from '@/types/workflowAI';
import { TaskRunEnvironments } from '../../runs/taskRunTable/TaskRunEnvironments';

type ProxyVersionPopoverItemProps = {
  version?: VersionV1;
  onClick?: () => void;
  className?: string;
};

function ProxyVersionPopoverItem(props: ProxyVersionPopoverItemProps) {
  const { version, onClick, className } = props;

  const environments = useMemo(() => environmentsForVersion(version), [version]);

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
          {environments && environments.length > 0 && <TaskRunEnvironments environments={environments} />}
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

type Props = {
  versions: VersionV1[];
  selectedVersionId: string | undefined;
  selectedEnvironment: VersionEnvironment | undefined;
  setSelectedEnvironmentAndVersionId: (
    environment: VersionEnvironment | undefined,
    versionId: string | undefined
  ) => void;
};

export function ProxyVersionPopover(props: Props) {
  const { versions, selectedVersionId, selectedEnvironment, setSelectedEnvironmentAndVersionId } = props;

  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const searchLower = search.toLowerCase();

  const sortedVersions = useMemo(() => {
    return sortVersionsTakingIntoAccountEnvironments(versions);
  }, [versions]);

  const filteredVersions = useMemo(() => {
    return sortedVersions.filter((version) => {
      const textBadge = formatSemverVersion(version);
      return textBadge?.includes(searchLower);
    });
  }, [sortedVersions, searchLower]);

  const selectedVersion = useMemo(() => {
    return versions.find((version) => version.id === selectedVersionId);
  }, [versions, selectedVersionId]);

  const onSelectedVersion = useCallback(
    (version: VersionV1 | undefined) => {
      if (!version) {
        setSelectedEnvironmentAndVersionId(undefined, undefined);
        setOpen(false);
        return;
      }

      const environment = environmentsForVersion(version)?.[0];
      setSelectedEnvironmentAndVersionId(environment, version.id);
      setOpen(false);
    },
    [setSelectedEnvironmentAndVersionId, setOpen]
  );

  const showTriggerVersionItem = !!selectedEnvironment || !!selectedVersionId;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div className='flex flex-row items-center gap-2 w-full border border-gray-300 bg-white rounded-[2px] min-h-10 px-3 shadow-sm cursor-pointer hover:bg-gray-100'>
          <div className='flex-1 min-w-0'>
            {showTriggerVersionItem ? (
              <ProxyVersionPopoverItem version={selectedVersion} className='px-0' />
            ) : (
              <div className='text-[12px] font-medium text-gray-500 truncate'>Select</div>
            )}
          </div>
          <ChevronsUpDown className='h-4 w-4 shrink-0 text-gray-500' />
        </div>
      </PopoverTrigger>
      <PopoverContent className='w-[350px] overflow-auto max-h-[300px] p-0 rounded-[2px]'>
        <CustomCommandInput placeholder='Search versions' search={search} onSearchChange={setSearch} />
        <div className='p-1'>
          {filteredVersions.length === 0 && <div className='text-sm text-center p-2'>No versions found</div>}
          {filteredVersions.map((version) => {
            return (
              <ProxyVersionPopoverItem key={version.id} version={version} onClick={() => onSelectedVersion(version)} />
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
