import { useMemo, useState } from 'react';
import { AIProviderIcon } from '@/components/icons/models/AIProviderIcon';
import { cn } from '@/lib/utils';
import { useOrFetchModels } from '@/store/fetchers';
import { ModelResponse } from '@/types/workflowAI';

type PriceSectionBarGraphProps = {
  percentage: number;
  price: number;
  color: string;
  providerName: string;
  subtitle: string;
};

function PriceSectionBarGraph(props: PriceSectionBarGraphProps) {
  const { percentage, price, color, providerName, subtitle } = props;

  return (
    <div className='flex sm:flex-row flex-col sm:gap-4 gap-1 w-full sm:items-center items-start'>
      <div className='sm:w-[112px] w-fit items-end text-right text-gray-500 text-[16px] font-medium'>
        {providerName}
      </div>
      <div className='flex flex-row gap-4 w-full h-full items-center'>
        <div className='flex flex-1 h-full'>
          <div className={cn('flex h-full', color)} style={{ width: `${percentage}%` }} />
        </div>
        <div className='w-[112px] flex flex-col justify-center sm:text-left text-right rounded-[2px]'>
          <div className='text-gray-700 text-[16px] font-medium'>${price}</div>
          <div className='text-gray-400 text-[12px] font-normal'>{subtitle}</div>
        </div>
      </div>
    </div>
  );
}

type PriceSectionGraphProps = {
  model: ModelResponse | undefined;
};

function PriceSectionGraph(props: PriceSectionGraphProps) {
  const { model } = props;

  if (!model) {
    return null;
  }

  const pricePerInputToken = model.metadata.price_per_input_token_usd * 1000000;

  const pricePerOutputToken = model.metadata.price_per_output_token_usd * 1000000;

  const maxPrice = Math.max(pricePerInputToken, pricePerOutputToken);

  return (
    <div className='flex flex-col w-full sm:gap-8 gap-4 bg-white sm:p-11 p-6'>
      <PriceSectionBarGraph
        percentage={90 * (pricePerInputToken / maxPrice)}
        price={pricePerInputToken}
        color='bg-indigo-200/60'
        providerName={model.metadata.provider_name}
        subtitle='/ 1M input tokens'
      />
      <PriceSectionBarGraph
        percentage={90 * (pricePerInputToken / maxPrice)}
        price={pricePerInputToken}
        color='bg-indigo-500'
        providerName='WorkflowAI'
        subtitle='/ 1M input tokens'
      />
      <PriceSectionBarGraph
        percentage={90 * (pricePerOutputToken / maxPrice)}
        price={pricePerOutputToken}
        color='bg-indigo-200/60'
        providerName={model.metadata.provider_name}
        subtitle='/ 1M output tokens'
      />
      <PriceSectionBarGraph
        percentage={90 * (pricePerOutputToken / maxPrice)}
        price={pricePerOutputToken}
        color='bg-indigo-500'
        providerName='WorkflowAI'
        subtitle='/ 1M output tokens'
      />
    </div>
  );
}

type PriceSectionModelSelectorItemProps = {
  model: ModelResponse;
  isSelected: boolean;
  onClick: () => void;
  numberOfModels: number;
};

function PriceSectionModelSelectorItem(props: PriceSectionModelSelectorItemProps) {
  const { model, isSelected, onClick } = props;

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center h-full sm:py-3 py-2 cursor-pointer border-b-2 shrink-0 sm:w-[25%] w-[148px]',
        isSelected
          ? 'text-gray-700 border-gray-700'
          : 'text-gray-500 border-gray-200 hover:border-gray-400 border-transparent hover:text-gray-600'
      )}
      onClick={onClick}
    >
      <div className='flex flex-row gap-[6px] items-center justify-center'>
        <AIProviderIcon name={model.metadata.provider_name} sizeClassName='w-[14px] h-[14px]' />
        <div className='text-[16px] font-semibold'>{model.metadata.provider_name}</div>
      </div>
      <div className='text-[12px] font-normal text-center px-1'>{model.name}</div>
    </div>
  );
}

type PriceSectionModelSelectorProps = {
  models: ModelResponse[] | undefined;
  selectedModelIndex: number | undefined;
  setSelectedModelIndex: (modelIndex: number) => void;
};

function PriceSectionModelSelector(props: PriceSectionModelSelectorProps) {
  const { models, selectedModelIndex, setSelectedModelIndex } = props;

  const numberOfModels = models?.length ?? 0;

  return (
    <div className='flex flex-row items-center sm:justify-center justify-start overflow-x-auto w-full scrollbar-hide border-b border-gray-200'>
      {models?.map((model, index) => (
        <PriceSectionModelSelectorItem
          key={model.id}
          model={model}
          isSelected={selectedModelIndex === index}
          onClick={() => setSelectedModelIndex(index)}
          numberOfModels={numberOfModels}
        />
      ))}
    </div>
  );
}

type Props = {
  className?: string;
};

export function PriceComponent(props: Props) {
  const { className } = props;

  const { models } = useOrFetchModels();

  const filteredModels = useMemo(() => {
    return models?.slice(0, 4);
  }, [models]);

  const [selectedModelIndex, setSelectedModelIndex] = useState<number>(0);

  return (
    <div className={cn('flex flex-col items-center sm:gap-8 gap-6 sm:px-16 px-4 w-full max-w-[1260px]', className)}>
      <div className='flex flex-col border border-gray-200 rounded-[2px] w-full'>
        <PriceSectionModelSelector
          models={filteredModels}
          selectedModelIndex={selectedModelIndex}
          setSelectedModelIndex={setSelectedModelIndex}
        />
        <PriceSectionGraph model={filteredModels?.[selectedModelIndex]} />
      </div>
    </div>
  );
}
