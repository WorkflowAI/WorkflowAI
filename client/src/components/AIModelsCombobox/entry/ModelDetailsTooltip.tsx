import { Tag16Regular } from '@fluentui/react-icons';
import { formatDate } from '@/lib/date';
import { formatCurrency, formatNumber } from '@/lib/formatters/numberFormatters';
import { ModelResponse } from '@/types/workflowAI';
import { PriceGraph } from './PriceGraph';

type ModelDetailsTooltipProps = {
  model: ModelResponse;
};

export function ModelDetailsTooltip(props: ModelDetailsTooltipProps) {
  const { model } = props;

  const contextWindowTokens = model.metadata?.context_window_tokens;
  const formattedContextWindow = !!contextWindowTokens ? formatNumber(contextWindowTokens) : '-';

  const price = model.average_cost_per_run_usd;
  const formettedPrice = price !== undefined && price !== null ? formatCurrency(price * 1000) : '-';

  const releaseDate = formatDate(model.metadata?.release_date, 'MMM DD, YYYY');

  const intelligence = !!model.metadata?.quality_index ? `${model.metadata.quality_index}` : '-';

  return (
    <div className='flex flex-col w-[280px] bg-gray-800'>
      <div className='flex flex-col items-start p-3 w-full'>
        <div className='text-[12px] text-gray-500 font-normal'>Model</div>
        <div className='text-[13px] font-medium text-white pb-2 border-b border-gray-700 w-full'>{model.name}</div>

        <div className='flex flex-row w-full border-b border-gray-700'>
          <div className='flex flex-col w-[50%] py-2 border-r border-gray-700'>
            <div className='text-[12px] text-gray-500 font-normal'>Context Window</div>
            <div className='text-[13px] font-medium text-white'>{formattedContextWindow}</div>
          </div>
          <div className='flex flex-col w-[50%] py-2 pl-3'>
            <div className='text-[12px] text-gray-500 font-normal'>Price</div>
            <div className='text-[13px] font-medium text-white flex flex-row items-baseline'>
              {formettedPrice}
              {!!price && <div className='text-gray-500 text-[12px]'>/1k runs</div>}
            </div>
          </div>
        </div>

        <div className='flex flex-row w-full'>
          <div className='flex flex-col w-[50%] py-2 border-r border-gray-700'>
            <div className='text-[12px] text-gray-500 font-normal'>Intelligence</div>
            <div className='text-[13px] font-medium text-white'>{intelligence}</div>
          </div>
          <div className='flex flex-col w-[50%] py-2 pl-3'>
            <div className='text-[12px] text-gray-500 font-normal'>Release Date</div>
            <div className='text-[13px] font-medium text-white'>{releaseDate}</div>
          </div>
        </div>
      </div>

      <div className='flex flex-col gap-2 p-3 w-full bg-gray-900/50'>
        <div className='flex flex-row text-[12px] text-gray-300 bg-gray-700 rounded-[3px] font-medium pl-1 pr-1.5 py-1 w-fit items-center gap-1'>
          <Tag16Regular className='w-4 h-4' />
          Price Match
        </div>
        <div className='text-[12px] text-gray-400 font-normal'>
          This model is priced the same on WorkflowAI as it is to use directly through a provider.
        </div>

        {!!price && <PriceGraph price={price * 1000} />}
      </div>
    </div>
  );
}
