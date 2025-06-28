import { BrainCircuitRegular, Copy16Regular } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { Check } from 'lucide-react';
import Image from 'next/image';
import * as React from 'react';
import { useCallback, useMemo, useState } from 'react';
import { useCopyToClipboard } from 'usehooks-ts';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { displaySuccessToaster } from '@/components/ui/Sonner';
import { formatDate } from '@/lib/date';
import { useAutoScrollRef } from '@/lib/hooks/useAutoScrollRef';
import { isModelSupportingResoning } from '@/lib/modelUtils';
import { cn } from '@/lib/utils';
import { TaskID } from '@/types/aliases';
import { ModelResponse } from '@/types/workflowAI';
import { SimpleTooltip } from '../../ui/Tooltip';
import { TaskCostBadge } from '../../v2/TaskCostBadge';
import { AIModelComboboxOption } from '../utils';
import { IntelliganceProgress } from './IntelliganceProgress';
import { ModelDetailsTooltip } from './ModelDetailsTooltip';
import { ResoningSelector } from './ResoningSelector';

type ComboboxModelEntryProps = {
  taskId?: TaskID;
  isSelected: boolean;
  showCheck?: boolean;
  model: ModelResponse;
  reasoning?: string | undefined;
  dropdownOpen: boolean | undefined;
  information: 'price' | 'intelligence' | 'latest';
  allIntelligenceScores: number[] | undefined;
  isProxy?: boolean;
  mode: 'popover' | 'selected';
  onReasoningChange?: (reasoning: string | undefined) => void;
};

export function ComboboxModelEntry(props: ComboboxModelEntryProps) {
  const {
    isSelected,
    showCheck = true,
    model,
    reasoning,
    dropdownOpen,
    information,
    allIntelligenceScores,
    isProxy,
    mode,
    onReasoningChange,
  } = props;
  const disabled = !!model.is_not_supported_reason;

  const autoScrollRef = useAutoScrollRef({
    isSelected,
    dropdownOpen,
  });

  const price = model.average_cost_per_run_usd;
  const releaseDate = formatDate(model.metadata?.release_date, 'MMM DD');
  const intelligence = model.metadata?.quality_index;

  const notSupportedText = 'is_not_supported_reason' in model ? model.is_not_supported_reason : undefined;

  const [isHovering, setIsHovering] = useState(false);
  const [, copy] = useCopyToClipboard();

  const isModelSupportingReasoning = useMemo(() => {
    return isModelSupportingResoning(model);
  }, [model]);

  const onCopyModelId = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      event.stopPropagation();
      copy(model.id);
      displaySuccessToaster('Copied to clipboard');
    },
    [model.id, copy]
  );

  return (
    <SimpleTooltip
      content={!!notSupportedText ? notSupportedText : showCheck && <ModelDetailsTooltip model={model} />}
      side={!notSupportedText ? 'right' : undefined}
      align={!notSupportedText ? 'center' : undefined}
      tooltipDelay={0}
      tooltipClassName={!notSupportedText ? 'm-3 p-0' : undefined}
    >
      <div
        className={cx(
          'flex items-center gap-2 min-w-[50px]',
          disabled && 'opacity-50',
          showCheck ? 'w-[288px]' : 'w-full'
        )}
        ref={autoScrollRef}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
      >
        {showCheck && <Check className={cn('h-4 w-4 text-indigo-600 flex-shrink-0', !isSelected && 'opacity-0')} />}
        <div className='w-6 h-6 rounded-[2px] bg-white flex items-center justify-center border border-gray-100'>
          <Image src={model.icon_url} alt='' width={20} height={20} className='w-4 h-4 flex-shrink-0' />
        </div>
        <div className='flex-1 flex items-center gap-0.5 overflow-hidden'>
          <div className='overflow-hidden text-ellipsis truncate whitespace-nowrap text-gray-900 text-[13px] font-normal'>
            {model.name}
          </div>
          {isHovering && isProxy && mode === 'selected' && (
            <SimpleTooltip
              content={
                <div>
                  <span>Copy model id: </span>
                  <span className='text-gray-300'>{model.id}</span>
                </div>
              }
              side='top'
              tooltipDelay={0}
            >
              <Button
                variant='newDesignGray'
                size='none'
                icon={<Copy16Regular />}
                className='w-5 h-5'
                onClick={onCopyModelId}
              />
            </SimpleTooltip>
          )}
          {mode === 'popover' && isModelSupportingReasoning && (
            <SimpleTooltip content={'Reasoning model'} side='top' tooltipDelay={0}>
              <Button
                variant='newDesignGray'
                size='none'
                icon={<BrainCircuitRegular className='text-gray-900 w-4 h-4' />}
                className='w-5 h-5 bg-clear'
              />
            </SimpleTooltip>
          )}
        </div>
        <div className='ml-auto flex flex-row gap-1 items-center'>
          {isModelSupportingReasoning && mode === 'selected' && onReasoningChange && (
            <ResoningSelector reasoning={reasoning} onReasoningChange={onReasoningChange} model={model} />
          )}
          {information === 'price' && (
            <TaskCostBadge
              cost={price}
              className=' border-gray-200 bg-gray-50 rounded-[2px] text-gray-500 text-[13px] font-medium py-0 px-[5px]'
              supportTooltip={true}
            />
          )}
          {information === 'latest' && (
            <Badge
              variant='tertiary'
              className='w-fit border-gray-200 bg-gray-50 rounded-[2px] text-gray-500 text-[13px] font-medium py-0 px-[5px] flex-shrink-0 whitespace-nowrap'
            >
              {releaseDate}
            </Badge>
          )}
          {information === 'intelligence' && !!intelligence && (
            <IntelliganceProgress intelligence={intelligence} allIntelligenceScores={allIntelligenceScores} />
          )}
        </div>
      </div>
    </SimpleTooltip>
  );
}

export function formatAIModels(aiModels: ModelResponse[]): AIModelComboboxOption[] {
  const allIntelligenceScores: number[] = [];

  aiModels.forEach((model) => {
    const intelligence = model.metadata?.quality_index;
    if (intelligence !== null && intelligence !== undefined) {
      allIntelligenceScores.push(intelligence);
    }
  });

  return aiModels.map((model) => ({
    model: model,
    value: model.id,
    label: model.name,
    disabled: !!model.is_not_supported_reason,
    isLatest: model.is_latest ?? true,
  }));
}

export function formatAIModel(model: ModelResponse, allModels: ModelResponse[]): AIModelComboboxOption {
  const allIntelligenceScores: number[] = [];

  allModels.forEach((model) => {
    const intelligence = model.metadata?.quality_index;
    if (intelligence !== null && intelligence !== undefined) {
      allIntelligenceScores.push(intelligence);
    }
  });

  const result: AIModelComboboxOption = {
    model: model,
    value: model.id,
    label: model.name,
    disabled: !!model.is_not_supported_reason,
    isLatest: model.is_latest ?? true,
  };

  return result;
}
