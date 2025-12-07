import * as amplitude from '@amplitude/analytics-browser';
import { AddFilled, ChevronUpDownFilled } from '@fluentui/react-icons';
import { Check } from 'lucide-react';
import { useCallback, useState } from 'react';
import { useMemo } from 'react';
import { PublicPrivateIcon } from '@/components/PublicPrivateIcon';
import { TaskSchemaBadgeContainer } from '@/components/TaskSchemaBadge/TaskSchemaBadgeContainer';
import { Button } from '@/components/ui/Button';
import { ComboboxOption } from '@/components/ui/Combobox';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
  CustomCommandInput,
} from '@/components/ui/Command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/Popover';
import { NEW_PROXY_AGENT_MODAL_OPEN, useQueryParamModal } from '@/lib/globalModal';
import { useAutoScrollRef } from '@/lib/hooks/useAutoScrollRef';
import { useDefaultRedirectRoute } from '@/lib/hooks/useTaskParams';
import { cn } from '@/lib/utils';
import { TaskID, TaskSchemaID } from '@/types/aliases';
import { SerializableTask } from '@/types/workflowAI';
import { TaskSchemaCommandLists } from './TaskSchemaCommandList';

export type TaskComboboxOption = ComboboxOption & {
  isPublic: boolean;
  key: string;
};

type TaskNameCommandListProps = {
  taskOptions: TaskComboboxOption[];
  onTaskChange: (value: TaskID) => void;
  setOpen: (value: boolean) => void;
  currentTaskId: TaskID | undefined;
  dropdownOpen: boolean;
};

export function TaskNameCommandList(props: TaskNameCommandListProps) {
  const { taskOptions, onTaskChange, setOpen, currentTaskId, dropdownOpen } = props;

  const selectedRef = useAutoScrollRef({
    isSelected: !!currentTaskId,
    dropdownOpen,
  });

  return (
    <CommandList className='max-h-max'>
      <CommandGroup>
        {taskOptions.map((taskOption) => (
          <CommandItem
            key={taskOption.value}
            value={taskOption.value}
            ref={currentTaskId === taskOption.value ? selectedRef : undefined}
            onSelect={() => {
              const currentValue = taskOption.value as TaskID;
              if (currentValue !== currentTaskId) {
                onTaskChange(currentValue);
              }
              setOpen(false);
            }}
            className='flex items-center gap-2 max-w-[280px] py-1.5'
          >
            <Check
              size={16}
              className={cn(
                'text-indigo-600 shrink-0',
                currentTaskId === taskOption.value ? 'opacity-100' : 'opacity-0'
              )}
            />
            <PublicPrivateIcon isPublic={taskOption.isPublic} />
            <div
              title={taskOption.label}
              className='overflow-hidden text-ellipsis whitespace-nowrap max-w-full text-gray-700 text-[13px] truncate shrink-1'
            >
              {taskOption.label}
            </div>
          </CommandItem>
        ))}
      </CommandGroup>
    </CommandList>
  );
}

export enum TaskSwitcherMode {
  TASKS = 'tasks',
  SCHEMAS = 'schemas',
  TASKS_AND_SCHEMAS = 'tasks_and_schemas',
}

type TaskSwitcherProps = {
  mode: TaskSwitcherMode;
  trigger: React.ReactNode | undefined;
  currentTask: SerializableTask | undefined;
  currentTaskSchemaId: TaskSchemaID | undefined;
  taskSchemaIds: TaskSchemaID[] | undefined;
  hiddenSchemaIds: TaskSchemaID[] | undefined;
  activeSchemaIds: TaskSchemaID[] | undefined;
  taskOptions: TaskComboboxOption[];
  onTaskChange: (value: TaskID) => void;
  onTaskSchemaChange: (value: TaskSchemaID) => void;
  checkIfSignedIn: () => boolean;
  open: boolean;
  setOpen: (value: boolean) => void;
  titleForFeatures?: string;
};

export function TaskSwitcher(props: TaskSwitcherProps) {
  const {
    mode,
    trigger,
    currentTask,
    currentTaskSchemaId,
    taskSchemaIds,
    hiddenSchemaIds,
    activeSchemaIds,
    taskOptions,
    onTaskChange,
    onTaskSchemaChange,
    checkIfSignedIn,
    open,
    setOpen,
    titleForFeatures,
  } = props;
  const currentTaskId = currentTask?.id as TaskID | undefined;
  const currentTaskName = currentTask?.name;

  const { openModal: openNewTaskModal } = useQueryParamModal(NEW_PROXY_AGENT_MODAL_OPEN);

  const onNewTaskClick = useCallback(() => {
    if (!checkIfSignedIn()) return;
    openNewTaskModal();
    amplitude.track('user.clicked.new_task');
    setOpen(false);
  }, [openNewTaskModal, checkIfSignedIn, setOpen]);
  const defaultRoute = useDefaultRedirectRoute();

  const close = useCallback(() => {
    setOpen(false);
  }, [setOpen]);

  const label = currentTaskName || 'Select an AI Agent';

  const [search, setSearch] = useState('');
  const filteredTaskOptions = useMemo(
    () => taskOptions.filter((option) => option.key.toLowerCase().includes(search.toLowerCase())),
    [taskOptions, search]
  );

  const filteredTaskSchemaIds = useMemo(() => {
    if (mode === TaskSwitcherMode.TASKS || mode === TaskSwitcherMode.TASKS_AND_SCHEMAS) {
      return taskSchemaIds;
    }
    return taskSchemaIds?.filter((id) => id.toString().includes(search.toLowerCase()));
  }, [taskSchemaIds, search, mode]);

  const filteredHiddenSchemaIds = useMemo(() => {
    if (mode === TaskSwitcherMode.TASKS || mode === TaskSwitcherMode.TASKS_AND_SCHEMAS) {
      return hiddenSchemaIds;
    }
    return hiddenSchemaIds?.filter((id) => id.toString().includes(search.toLowerCase()));
  }, [hiddenSchemaIds, search, mode]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        {!!trigger ? (
          trigger
        ) : (
          <Button
            variant='newDesign'
            role='combobox'
            aria-expanded={open}
            className='h-10.5 w-full justify-between pl-[10px] pr-3 font-lato gap-2 border-gray-300 shadow-sm'
          >
            <div className='flex items-center gap-2 overflow-hidden w-full'>
              <div className='flex items-center gap-2.5 w-full'>
                <div className='truncate text-gray-800 text-[13px]' title={label}>
                  {label}
                </div>
              </div>
            </div>
            {!!currentTaskSchemaId && (
              <TaskSchemaBadgeContainer
                schemaId={currentTaskSchemaId}
                isActive={activeSchemaIds?.includes(currentTaskSchemaId)}
              />
            )}
            <ChevronUpDownFilled className='h-4 w-4 shrink-0 text-gray-500' />
          </Button>
        )}
      </PopoverTrigger>
      <PopoverContent className='w-[auto] p-0 rounded-[2px] border-gray-300 font-lato' align='start'>
        <Command>
          <CustomCommandInput
            placeholder={mode === TaskSwitcherMode.SCHEMAS ? 'Search Schemas...' : 'Search AI Agents...'}
            search={search}
            onSearchChange={setSearch}
          />
          <div className='max-h-[50vh] overflow-y-auto'>
            {mode !== TaskSwitcherMode.TASKS && (
              <div className='flex flex-col'>
                <CommandEmpty>No schema found</CommandEmpty>
                <TaskSchemaCommandLists
                  taskSchemaIds={filteredTaskSchemaIds}
                  hiddenSchemaIds={filteredHiddenSchemaIds}
                  activeSchemaIds={activeSchemaIds}
                  currentTaskSchemaId={currentTaskSchemaId}
                  onTaskSchemaChange={onTaskSchemaChange}
                  setOpen={setOpen}
                />
              </div>
            )}

            {mode !== TaskSwitcherMode.SCHEMAS && (
              <div className='flex flex-col'>
                <div className='px-1.5 py-2 text-gray-700 text-[13px] font-semibold border-b border-gray-200'>
                  <div
                    className='flex items-center px-2 py-1.5 gap-2 bg-gray-100 hover:bg-gray-200 rounded-[2px] cursor-pointer'
                    onClick={onNewTaskClick}
                  >
                    <AddFilled className='h-4 w-4 shrink-0' />
                    New
                  </div>
                </div>
                <div className='w-auto flex items-center justify-between pl-3 pr-1 pt-2 font-lato'>
                  <div className='text-indigo-600 text-xs font-medium uppercase'>{titleForFeatures ?? 'AI Agents'}</div>
                  <Button variant='newDesign' className='h-7 px-2 text-xs' toRoute={defaultRoute} onClick={close}>
                    See all
                  </Button>
                </div>
                <CommandEmpty>No task found</CommandEmpty>
                <TaskNameCommandList
                  taskOptions={filteredTaskOptions}
                  onTaskChange={onTaskChange}
                  setOpen={setOpen}
                  currentTaskId={currentTaskId}
                  dropdownOpen={open}
                />
              </div>
            )}
          </div>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
