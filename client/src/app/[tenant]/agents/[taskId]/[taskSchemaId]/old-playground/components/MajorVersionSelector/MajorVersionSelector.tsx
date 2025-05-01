import { Checkmark16Filled, ChevronUpDownFilled } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useMemo } from 'react';
import { CommandGroup, CommandItem, CustomCommandInput } from '@/components/ui/Command';
import { CommandList } from '@/components/ui/Command';
import { Command } from '@/components/ui/Command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/Popover';
import { ScrollArea } from '@/components/ui/ScrollArea';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { getEnvironmentsForMajorVersion } from '@/lib/versionUtils';
import { MajorVersion } from '@/types/workflowAI';
import { TaskRunEnvironments } from '../../../runs/taskRunTable/TaskRunEnvironments';
import { MajorVersionDetails } from './MajorVersionDetails';

type MajorVersionComboboxProps = {
  majorVersions: MajorVersion[];
  matchedMajorVersion: MajorVersion | undefined;
  useInstructionsAndTemperatureFromMajorVersion: (version: MajorVersion) => void;
};

function searchValueForVersion(version: MajorVersion | undefined, newestMajorVersion: number | undefined) {
  if (!version) {
    return undefined;
  }

  const environments = getEnvironmentsForMajorVersion(version);
  const environmentNames = environments?.join(', ');

  const lastestText = version.major === newestMajorVersion ? 'latest' : '';
  return `Version ${version.major} ${lastestText} ${environmentNames}`.toLowerCase();
}

type MajorVersionDoubleBadgeProps = {
  version: MajorVersion;
  newestMajorVersion: number;
};

function MajorVersionDoubleBadge(props: MajorVersionDoubleBadgeProps) {
  const { version, newestMajorVersion } = props;

  const environments = useMemo(() => {
    return getEnvironmentsForMajorVersion(version);
  }, [version]);

  return (
    <div className='flex flex-row gap-2 items-center'>
      <div className='text-gray-600 text-[13px] font-medium px-1.5 py-0.5 rounded-[2px] border border-gray-200 bg-white'>
        Version {version.major}
      </div>
      {version.major === newestMajorVersion && (
        <div className='text-gray-50 text-[13px] font-medium px-1.5 py-0.5 rounded-[2px] bg-gray-700'>Latest</div>
      )}
      {!!environments && <TaskRunEnvironments environments={environments} />}
    </div>
  );
}

type MajorVersionComboboxEntryProps = {
  version: MajorVersion | undefined;
  newestMajorVersion: number;
  trigger: boolean;
  isSelected: boolean;
};

function MajorVersionComboboxEntry(props: MajorVersionComboboxEntryProps) {
  const { version, newestMajorVersion, trigger, isSelected } = props;

  if (!version) {
    return (
      <div className='text-gray-400 text-[14px] font-medium h-[26px] flex items-center cursor-pointer'>
        Select parameters from a version
      </div>
    );
  }

  if (trigger) {
    return (
      <div className='flex flex-row gap-2 items-center cursor-pointer'>
        <div className='text-gray-800 text-[14px] font-medium'>From</div>
        <MajorVersionDoubleBadge version={version} newestMajorVersion={newestMajorVersion} />
      </div>
    );
  }

  return (
    <div className='flex relative w-full cursor-pointer'>
      <SimpleTooltip
        content={<MajorVersionDetails majorVersion={version} />}
        side='left'
        align='start'
        tooltipDelay={100}
        tooltipClassName='mx-3 -my-1 p-0 bg-white'
      >
        <div className='flex flex-row gap-2 items-center w-full'>
          <Checkmark16Filled
            className={cx('h-4 w-4 shrink-0 text-indigo-600', isSelected ? 'opacity-100' : 'opacity-0')}
          />
          <MajorVersionDoubleBadge version={version} newestMajorVersion={newestMajorVersion} />
        </div>
      </SimpleTooltip>
    </div>
  );
}

export function MajorVersionCombobox(props: MajorVersionComboboxProps) {
  const {
    majorVersions,
    matchedMajorVersion,
    useInstructionsAndTemperatureFromMajorVersion: setInstructionsAndTemperature,
  } = props;
  const [search, setSearch] = useState('');

  const sortedMajorVersions: MajorVersion[] = useMemo(() => {
    return majorVersions.sort((a, b) => b.major - a.major);
  }, [majorVersions]);

  const newestMajorVersion: number | undefined = sortedMajorVersions[0]?.major;

  const filteredMajorVersions = useMemo(() => {
    return sortedMajorVersions.filter((version) => {
      const text = searchValueForVersion(version, newestMajorVersion);
      return text ? text.includes(search.toLowerCase()) : false;
    });
  }, [sortedMajorVersions, search, newestMajorVersion]);

  const [open, setOpen] = useState(false);

  const currentSearchValue = useMemo(
    () => searchValueForVersion(matchedMajorVersion, newestMajorVersion),
    [matchedMajorVersion, newestMajorVersion]
  );

  const commandListRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && currentSearchValue && commandListRef.current) {
      const item = commandListRef.current.querySelector(`[cmdk-item][data-value="${currentSearchValue}"]`);
      if (item) {
        item.scrollIntoView({ block: 'center' });
      }
    }
  }, [matchedMajorVersion, open, currentSearchValue]);

  const selectVersion = useCallback(
    (version: MajorVersion) => {
      setInstructionsAndTemperature(version);
      setOpen(false);
    },
    [setInstructionsAndTemperature, setOpen]
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div
          className={cx(
            'flex flex-row py-1.5 pl-3 pr-2.5 cursor-pointer items-center border border-gray-200/50 rounded-[2px] text-sm font-normal font-lato truncate min-w-[75px] justify-between',
            open
              ? 'border-gray-300 bg-gray-100 shadow-inner'
              : 'bg-white text-gray-900 border-gray-300 shadow-sm border border-input bg-background hover:bg-gray-100'
          )}
        >
          <MajorVersionComboboxEntry
            version={matchedMajorVersion}
            newestMajorVersion={newestMajorVersion}
            trigger={true}
            isSelected={false}
          />
          <ChevronUpDownFilled className='h-4 w-4 shrink-0 text-gray-500 ml-2' />
        </div>
      </PopoverTrigger>

      <PopoverContent className='w-[auto] p-0 overflow-clip rounded-[2px]' align='end' side='bottom' sideOffset={5}>
        <Command>
          <CustomCommandInput placeholder={'Search...'} search={search} onSearchChange={setSearch} />
          {filteredMajorVersions.length === 0 && (
            <div className='flex w-full h-[80px] items-center justify-center text-gray-500 text-[13px] font-medium'>
              No versions found
            </div>
          )}
          <ScrollArea>
            <CommandList ref={commandListRef}>
              <CommandGroup key='models'>
                {filteredMajorVersions.map((version) => (
                  <CommandItem
                    key={version.major}
                    value={searchValueForVersion(version, newestMajorVersion)}
                    onSelect={() => selectVersion(version)}
                  >
                    <MajorVersionComboboxEntry
                      version={version}
                      newestMajorVersion={newestMajorVersion}
                      trigger={false}
                      isSelected={version.major === matchedMajorVersion?.major}
                    />
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </ScrollArea>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
