import { cx } from 'class-variance-authority';
import { Check } from 'lucide-react';
import Image from 'next/image';
import * as React from 'react';
import { Badge } from '@/components/ui/Badge';
import { formatDate } from '@/lib/date';
import { useAutoScrollRef } from '@/lib/hooks/useAutoScrollRef';
import { cn } from '@/lib/utils';
import { ModelResponse } from '@/types/workflowAI';
import { SimpleTooltip } from '../../ui/Tooltip';
import { TaskCostBadge } from '../../v2/TaskCostBadge';
import { AIModelComboboxOption } from '../utils';
import { IntelliganceProgress } from './IntelliganceProgress';
import { ModelDetailsTooltip } from './ModelDetailsTooltip';

type ModelLabelProps = {
  isSelected: boolean;
  showCheck?: boolean;
  model: ModelResponse;
  dropdownOpen: boolean | undefined;
  information: 'price' | 'intelligence' | 'latest';
  allIntelligenceScores: number[] | undefined;
};

export function ModelLabel(props: ModelLabelProps) {
  const { isSelected, showCheck = true, model, dropdownOpen, information, allIntelligenceScores } = props;
  const disabled = !!model.is_not_supported_reason;

  const autoScrollRef = useAutoScrollRef({
    isSelected,
    dropdownOpen,
  });

  const price = model.average_cost_per_run_usd;
  const releaseDate = formatDate(model.metadata?.release_date, 'MMM DD');
  const intelligence = model.metadata?.quality_index;

  const notSupportedText = 'is_not_supported_reason' in model ? model.is_not_supported_reason : undefined;

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
      >
        {showCheck && <Check className={cn('h-4 w-4 text-indigo-600 flex-shrink-0', !isSelected && 'opacity-0')} />}
        <div className='w-6 h-6 rounded-[2px] bg-white flex items-center justify-center border border-gray-100'>
          <Image src={model.icon_url} alt='' width={20} height={20} className='w-4 h-4 flex-shrink-0' />
        </div>
        <div className='overflow-hidden text-ellipsis truncate whitespace-nowrap text-gray-900 text-[13px] font-normal flex-1'>
          {model.name}
        </div>
        <div className='ml-auto flex flex-row gap-1'>
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

export function formatAIModels(
  aiModels: ModelResponse[] | undefined,
  information: 'price' | 'intelligence' | 'latest'
): AIModelComboboxOption[] {
  if (!aiModels) {
    return [];
  }

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
    renderLabel: ({ isSelected, showCheck = true, dropdownOpen }) => (
      <ModelLabel
        isSelected={isSelected}
        showCheck={showCheck}
        model={model}
        dropdownOpen={dropdownOpen}
        information={information}
        allIntelligenceScores={allIntelligenceScores}
      />
    ),
  }));
}

export function formatAIModel(
  model: ModelResponse,
  allModels: ModelResponse[] | undefined,
  information: 'price' | 'intelligence' | 'latest'
): AIModelComboboxOption {
  const allIntelligenceScores: number[] = [];

  allModels?.forEach((model) => {
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
    renderLabel: ({ isSelected, showCheck = true, dropdownOpen }) => (
      <ModelLabel
        isSelected={isSelected}
        showCheck={showCheck}
        model={model}
        dropdownOpen={dropdownOpen}
        information={information}
        allIntelligenceScores={allIntelligenceScores}
      />
    ),
  };

  return result;
}
