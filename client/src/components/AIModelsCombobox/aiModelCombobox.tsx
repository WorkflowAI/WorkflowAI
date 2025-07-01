import { Calendar16Regular, ChevronUpDownFilled, Sparkle16Regular, Tag16Regular } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { Command as CommandPrimitive } from 'cmdk';
import * as React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocalStorage } from 'usehooks-ts';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
  CustomCommandInput,
} from '@/components/ui/Command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/Popover';
import { ScrollArea } from '@/components/ui/ScrollArea';
import { embedReasoningInModelID } from '@/lib/modelUtils';
import { Model, TaskID } from '@/types/aliases';
import { ModelResponse } from '@/types/workflowAI';
import { MysteryModelIcon } from '../icons/models/mysteryModelIcon';
import { SimpleTooltip } from '../ui/Tooltip';
import { SortButton } from './SortButton';
import { ComboboxModelEntry, formatAIModel, formatAIModels } from './entry/ComboboxModelEntry';
import { AIModelComboboxOption, modelComparator } from './utils';

type TriggerContentProps = {
  value: string;
  selectedOption: AIModelComboboxOption | undefined;
  defaultLabel: string;
  isProxy?: boolean;
  taskId?: TaskID;
};

function TriggerContent(props: TriggerContentProps) {
  const { value, selectedOption, defaultLabel, isProxy, taskId } = props;
  if (!value) {
    return (
      <div className='flex items-center gap-2'>
        <MysteryModelIcon />
        {defaultLabel}
      </div>
    );
  }
  if (selectedOption) {
    return (
      <ComboboxModelEntry
        isSelected={true}
        showCheck={false}
        model={selectedOption.model}
        dropdownOpen={undefined}
        information='price'
        allIntelligenceScores={undefined}
        isProxy={isProxy}
        taskId={taskId}
        mode='selected'
      />
    );
  }
  return defaultLabel;
}

export type AIModelComboboxProps = {
  disabled?: boolean;
  emptyMessage?: string;
  noOptionsMessage?: string;
  onModelChange: (value: Model) => void;
  models: ModelResponse[];
  placeholder?: string;
  value: string;
  fitToContent?: boolean;
  open?: boolean;
  setOpen?: (open: boolean) => void;
  isProxy?: boolean;
  taskId?: TaskID;
  spreadReasoning?: boolean;
  reasoningEffort?: string;
};

export function AIModelCombobox(props: AIModelComboboxProps) {
  const {
    disabled,
    emptyMessage = 'No option found',
    noOptionsMessage = 'Choose Model',
    onModelChange,
    models,
    placeholder: placeholderFromParameters,
    value: rawValue,
    fitToContent = true,
    open: propsOpen,
    setOpen: propsSetOpen,
    isProxy = false,
    taskId,
    spreadReasoning,
    reasoningEffort,
  } = props;
  const [internalOpen, setInternalOpen] = React.useState(false);

  const open = propsOpen !== undefined ? propsOpen : internalOpen;
  const setOpen = propsSetOpen !== undefined ? propsSetOpen : setInternalOpen;

  const [search, setSearch] = useState('');

  const [sort, setSort] = useLocalStorage<'intelligence' | 'price' | 'latest'>('aiModelComboboxSort', 'intelligence');

  const [isReverted, setIsReverted] = useLocalStorage<boolean>('aiModelComboboxOrder', false);

  const modelOptions = useMemo(() => formatAIModels(models, spreadReasoning ?? false), [models, spreadReasoning]);

  const placeholder = useMemo(() => {
    if (placeholderFromParameters) {
      return placeholderFromParameters;
    }
    return `Search through ${modelOptions.length} models`;
  }, [placeholderFromParameters, modelOptions]);

  const displayedModelOptions = useMemo(() => {
    if (!search) {
      // By default we only return models that have the is_latest flag
      return modelOptions.filter((model) => model.isLatest);
    }
    return modelOptions.filter((option) => option.label.toLowerCase().includes(search.toLowerCase()));
  }, [modelOptions, search]);

  const value = useMemo(() => {
    if (reasoningEffort && spreadReasoning) {
      return embedReasoningInModelID(rawValue, reasoningEffort);
    }
    return rawValue;
  }, [rawValue, reasoningEffort, spreadReasoning]);

  const selectedOption = useMemo(() => {
    const option = modelOptions.find((option) => option.value === value);
    if (option) {
      return formatAIModel(option.model);
    }
    return undefined;
  }, [modelOptions, value]);

  const sortedModelOptions = useMemo(() => {
    const comparator = modelComparator(sort, isReverted);
    return displayedModelOptions.sort(comparator);
  }, [displayedModelOptions, sort, isReverted]);

  const onSelect = useCallback(
    (selectedValue: string, disabled?: boolean) => {
      if (disabled) {
        return;
      }
      if (selectedValue !== value) {
        onModelChange(selectedValue as Model);
      }
      setOpen(false);
    },
    [onModelChange, setOpen, value]
  );

  const onSortChange = useCallback(
    (newSort: 'intelligence' | 'price' | 'latest') => {
      if (sort === newSort) {
        setIsReverted(!isReverted);
      } else {
        setSort(newSort);
        setIsReverted(false);
      }
    },
    [setSort, setIsReverted, isReverted, sort]
  );

  const commandListRef = useRef<React.ElementRef<typeof CommandPrimitive.List>>(null);

  useEffect(() => {
    if (open && value && commandListRef.current) {
      const item = commandListRef.current.querySelector(`[cmdk-item][data-value="${value}"]`);
      if (item) {
        item.scrollIntoView({ block: 'center' });
      }
    }
  }, [sort, isReverted, open, value]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild disabled={disabled}>
        <div
          className={cx(
            'flex flex-row py-1.5 pl-3 pr-2.5 cursor-pointer items-center border border-gray-200/50 rounded-[2px] text-sm font-normal font-lato truncate',
            open
              ? 'border-gray-300 bg-gray-100 shadow-inner'
              : 'bg-white text-gray-900 border-gray-300 shadow-sm border border-input bg-background hover:bg-gray-100',
            fitToContent ? 'min-w-[75px] justify-between' : 'w-full justify-between'
          )}
        >
          <TriggerContent
            value={value}
            selectedOption={selectedOption}
            defaultLabel={noOptionsMessage}
            isProxy={isProxy}
            taskId={taskId}
          />
          <ChevronUpDownFilled className='h-4 w-4 shrink-0 text-gray-500 ml-2' />
        </div>
      </PopoverTrigger>

      <PopoverContent className='w-[auto] p-0 overflow-clip rounded-[2px]'>
        <Command>
          <CustomCommandInput placeholder={placeholder} search={search} onSearchChange={setSearch} />
          <CommandEmpty>{emptyMessage}</CommandEmpty>
          <ScrollArea>
            <div className='px-3 py-2 border-b border-gray-200 flex flex-row gap-2 items-center'>
              <SimpleTooltip
                content={`Sort by how well models\nbalance factual accuracy,\nrelevance, and clarity to\nproduce the most\nvaluable answer possible`}
                tooltipClassName='whitespace-break-spaces text-center'
                tooltipDelay={100}
              >
                <div>
                  <SortButton
                    icon={<Sparkle16Regular />}
                    text='Intelligence'
                    isOn={sort === 'intelligence'}
                    defaultOrder='descending'
                    revert={isReverted}
                    onSortChange={() => onSortChange('intelligence')}
                  />
                </div>
              </SimpleTooltip>
              <SimpleTooltip
                content={`Sort by how affordable it\nis for a model to run your\nAI agents`}
                tooltipClassName='whitespace-break-spaces text-center'
                tooltipDelay={100}
              >
                <div>
                  <SortButton
                    icon={<Tag16Regular />}
                    text='Price'
                    isOn={sort === 'price'}
                    defaultOrder='ascending'
                    revert={isReverted}
                    onSortChange={() => onSortChange('price')}
                  />
                </div>
              </SimpleTooltip>
              <SimpleTooltip
                content={`Sort by model release\ndate`}
                tooltipClassName='whitespace-break-spaces text-center'
                tooltipDelay={100}
              >
                <div>
                  <SortButton
                    icon={<Calendar16Regular />}
                    text='Latest'
                    isOn={sort === 'latest'}
                    defaultOrder='descending'
                    revert={isReverted}
                    onSortChange={() => onSortChange('latest')}
                  />
                </div>
              </SimpleTooltip>
            </div>
            <CommandList ref={commandListRef}>
              <CommandGroup key='models'>
                {sortedModelOptions.map((option) => (
                  <CommandItem
                    key={option.value}
                    value={option.value}
                    onSelect={() => onSelect(option.value, option.disabled)}
                    className='text-[13px] font-normal font-lato'
                  >
                    <ComboboxModelEntry
                      model={option.model}
                      information='price'
                      allIntelligenceScores={undefined}
                      isSelected={value === option.value}
                      dropdownOpen={open}
                      isProxy={isProxy}
                      taskId={taskId}
                      mode='popover'
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
