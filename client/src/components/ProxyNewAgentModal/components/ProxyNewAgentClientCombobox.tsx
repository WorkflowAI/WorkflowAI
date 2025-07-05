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

function iconURLForClient(client: string | undefined) {
  if (!client) {
    return undefined;
  }
  switch (client) {
    case 'Cursor':
      return 'https://workflowai.blob.core.windows.net/workflowai-public/CursorMCPIcon.png';
    case 'Windsurf':
      return 'https://workflowai.blob.core.windows.net/workflowai-public/WindsurfMCPIcon.png';
    case 'Claude Code':
      return 'https://workflowai.blob.core.windows.net/workflowai-public/ClaudeMCPIcon.png';
    case 'Github Copilot':
      return 'https://workflowai.blob.core.windows.net/workflowai-public/GithubMCPIcon.png';
    default:
      return undefined;
  }
}

function searchValueForClient(client: string | undefined) {
  if (!client) {
    return undefined;
  }
  return client.toLowerCase();
}

type ClientComboboxEntryProps = {
  client: string | undefined;
  trigger: boolean;
  isSelected: boolean;
  onClick?: () => void;
  className?: string;
};

function ClientComboboxEntry(props: ClientComboboxEntryProps) {
  const { client, trigger, isSelected, onClick, className } = props;

  if (!client) {
    return (
      <div className='text-gray-400 text-[14px] font-medium h-[32px] flex items-center cursor-pointer'>
        Select a client
      </div>
    );
  }

  const iconURL = iconURLForClient(client);

  if (trigger) {
    return (
      <div className='flex flex-row gap-2 items-center cursor-pointer py-1'>
        {iconURL && <Image src={iconURL} alt={client} width={16} height={16} />}
        <div className={cn('text-gray-800 text-[14px] font-medium', className)}>{client}</div>
      </div>
    );
  }

  return (
    <div className='flex relative w-full cursor-pointer hover:bg-gray-100 rounded-[2px] px-2' onClick={onClick}>
      <div className='flex flex-row gap-2 items-center w-full py-2'>
        <Checkmark16Filled
          className={cn('h-4 w-4 shrink-0 text-indigo-600', isSelected ? 'opacity-100' : 'opacity-0')}
        />
        {iconURL && <Image src={iconURL} alt={client} width={16} height={16} />}
        <div className={cn('text-gray-800 text-[14px] font-medium', className)}>{client}</div>
      </div>
    </div>
  );
}

type ProxyNewAgentClientComboboxProps = {
  clients: string[] | undefined;
  selectedClient: string | undefined;
  setSelectedClient: (client: string | undefined) => void;
  className?: string;
  entryClassName?: string;
};

export function ProxyNewAgentClientCombobox(props: ProxyNewAgentClientComboboxProps) {
  const { clients, selectedClient, setSelectedClient, className, entryClassName } = props;
  const [search, setSearch] = useState('');

  const filteredClients = useMemo(() => {
    if (!clients) {
      return [];
    }
    return clients.filter((client) => {
      const text = client;
      return text ? text.toLowerCase().includes(search.toLowerCase()) : false;
    });
  }, [clients, search]);

  const [open, setOpen] = useState(false);

  const currentSearchValue = useMemo(() => searchValueForClient(selectedClient), [selectedClient]);

  const commandListRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && currentSearchValue && commandListRef.current) {
      const item = commandListRef.current.querySelector(`[cmdk-item][data-value="${currentSearchValue}"]`);
      if (item) {
        item.scrollIntoView({ block: 'center' });
      }
    }
  }, [selectedClient, open, currentSearchValue]);

  const selectClient = useCallback(
    (client: string) => {
      setSelectedClient(client);
      setOpen(false);
    },
    [setSelectedClient, setOpen]
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
          <ClientComboboxEntry client={selectedClient} trigger={true} isSelected={false} className={entryClassName} />
          <ChevronUpDownFilled className='h-4 w-4 shrink-0 text-gray-500 ml-2' />
        </div>
      </PopoverTrigger>

      <PopoverContent
        className='p-0 overflow-clip rounded-[2px]'
        side='bottom'
        sideOffset={5}
        style={{ width: 'var(--radix-popover-trigger-width)' }}
      >
        <Command>
          <CustomCommandInput placeholder={'Search...'} search={search} onSearchChange={setSearch} />
          {filteredClients.length === 0 && (
            <div className='flex w-full h-[80px] items-center justify-center text-gray-500 text-[13px] font-medium mt-1'>
              No clients found
            </div>
          )}
          <ScrollArea>
            <div className='text-indigo-600 text-[12px] font-semibold px-3 pt-2 uppercase'>Select your MCP Client</div>
            <CommandList ref={commandListRef}>
              <CommandGroup key='clients'>
                {filteredClients.map((client) => (
                  <ClientComboboxEntry
                    key={client}
                    client={client}
                    trigger={false}
                    isSelected={client === selectedClient}
                    onClick={() => selectClient(client)}
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
