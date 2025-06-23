import { Checkmark16Filled, ChevronUpDownFilled } from '@fluentui/react-icons';
import Image from 'next/image';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useMemo } from 'react';
import { CommandGroup, CustomCommandInput } from '@/components/ui/Command';
import { CommandList } from '@/components/ui/Command';
import { Command } from '@/components/ui/Command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/Popover';
import { ScrollArea } from '@/components/ui/ScrollArea';
import { cn } from '@/lib/utils';
import { Integration } from '@/types/workflowAI/models';

function searchValueForIntegration(integration: Integration | undefined) {
  if (!integration) {
    return undefined;
  }
  return `${integration.display_name} ${integration.id} ${integration.programming_language}`.toLowerCase();
}

function isOpenAISdkIntegration(integration: Integration): boolean {
  const displayName = integration.display_name.toLowerCase();

  // Check if it's an OpenAI SDK integration by display name
  return displayName.includes('openai sdk');
}

type IntegrationComboboxEntryProps = {
  integration: Integration | undefined;
  trigger: boolean;
  isSelected: boolean;
  onClick?: () => void;
  className?: string;
};

function IntegrationComboboxEntry(props: IntegrationComboboxEntryProps) {
  const { integration, trigger, isSelected, onClick, className } = props;

  if (!integration) {
    return (
      <div className='text-gray-400 text-[14px] font-medium h-[32px] flex items-center cursor-pointer'>
        Select an integration
      </div>
    );
  }

  if (trigger) {
    return (
      <div className='flex flex-row gap-2 items-center cursor-pointer py-1'>
        <div className='flex items-center justify-center w-6 h-6 rounded-[2px] border border-gray-200 bg-white overflow-hidden'>
          <Image src={integration.logo_url} alt={integration.display_name} width={16} height={16} />
        </div>
        <div className={cn('text-gray-800 text-[14px] font-medium', className)}>{integration.display_name}</div>
      </div>
    );
  }

  return (
    <div className='flex relative w-full cursor-pointer hover:bg-gray-100 rounded-[2px] px-2' onClick={onClick}>
      <div className='flex flex-row gap-2 items-center w-full py-2'>
        <Checkmark16Filled
          className={cn('h-4 w-4 shrink-0 text-indigo-600', isSelected ? 'opacity-100' : 'opacity-0')}
        />
        <div className='flex items-center justify-center w-6 h-6 rounded-[2px] border border-gray-200 bg-white overflow-hidden'>
          <Image src={integration.logo_url} alt={integration.display_name} width={16} height={16} />
        </div>
        <div className={cn('text-gray-800 text-[14px] font-medium', className)}>{integration.display_name}</div>
      </div>
    </div>
  );
}

type IntegrationComboboxProps = {
  integrations: Integration[] | undefined;
  integrationId: string | undefined;
  setIntegrationId: (integrationId: string | undefined) => void;
  className?: string;
  entryClassName?: string;
  showOnlyOpenAISdk?: boolean;
};

export function IntegrationCombobox(props: IntegrationComboboxProps) {
  const { integrations, integrationId, setIntegrationId, className, entryClassName, showOnlyOpenAISdk = false } = props;
  const [search, setSearch] = useState('');

  const integration = useMemo(() => {
    return integrations?.find((integration) => integration.id === integrationId);
  }, [integrations, integrationId]);

  const filteredIntegrations = useMemo(() => {
    if (!integrations) {
      return [];
    }

    let availableIntegrations = integrations;

    // Filter to only OpenAI SDK integrations if required
    if (showOnlyOpenAISdk) {
      availableIntegrations = integrations.filter(isOpenAISdkIntegration);
    }

    // Apply search filter
    return availableIntegrations.filter((integration) => {
      const text = searchValueForIntegration(integration);
      return text ? text.includes(search.toLowerCase()) : false;
    });
  }, [integrations, search, showOnlyOpenAISdk]);

  const [open, setOpen] = useState(false);

  const currentSearchValue = useMemo(() => searchValueForIntegration(integration), [integration]);

  const commandListRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && currentSearchValue && commandListRef.current) {
      const item = commandListRef.current.querySelector(`[cmdk-item][data-value="${currentSearchValue}"]`);
      if (item) {
        item.scrollIntoView({ block: 'center' });
      }
    }
  }, [integration, open, currentSearchValue]);

  const selectIntegration = useCallback(
    (integration: Integration) => {
      setIntegrationId(integration.id);
      setOpen(false);
    },
    [setIntegrationId, setOpen]
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div
          className={cn(
            'flex flex-row py-1.5 pl-3 pr-2.5 cursor-pointer items-center border border-gray-200/50 rounded-[2px] text-sm font-normal font-lato truncate min-w-[75px] justify-between',
            open
              ? 'border-gray-300 bg-gray-100 shadow-inner'
              : 'bg-white text-gray-900 border-gray-300 shadow-sm border border-input bg-background hover:bg-gray-100',
            className
          )}
        >
          <IntegrationComboboxEntry
            integration={integration}
            trigger={true}
            isSelected={false}
            className={entryClassName}
          />
          <ChevronUpDownFilled className='h-4 w-4 shrink-0 text-gray-500 ml-2' />
        </div>
      </PopoverTrigger>

      <PopoverContent
        className='p-0 overflow-clip rounded-[2px]'
        side='top'
        sideOffset={5}
        style={{ width: 'var(--radix-popover-trigger-width)' }}
      >
        <Command>
          <CustomCommandInput placeholder={'Search...'} search={search} onSearchChange={setSearch} />
          {filteredIntegrations.length === 0 && (
            <div className='flex w-full h-[80px] items-center justify-center text-gray-500 text-[13px] font-medium mt-1'>
              {showOnlyOpenAISdk ? 'No OpenAI SDK integrations found' : 'No integrations found'}
            </div>
          )}
          <ScrollArea>
            <CommandList ref={commandListRef}>
              <CommandGroup key='models'>
                {filteredIntegrations.map((integration) => (
                  <IntegrationComboboxEntry
                    key={integration.id}
                    integration={integration}
                    trigger={false}
                    isSelected={integration.id === integrationId}
                    onClick={() => selectIntegration(integration)}
                    className={entryClassName}
                  />
                ))}
              </CommandGroup>
            </CommandList>
          </ScrollArea>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
