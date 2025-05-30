import { Money16Regular, Timer16Regular, Window16Regular } from '@fluentui/react-icons';
import { useMemo } from 'react';
import { ContextWindowProgressBar } from '@/components/ui/ContextWindowProgressBar';
import { formatFractionalCurrency } from '@/lib/formatters/numberFormatters';
import { getContextWindowInformation } from '@/lib/taskRunUtils';
import { LLMCompletionTypedMessages, RunV1 } from '@/types/workflowAI';

type Props = {
  run: RunV1 | undefined;
  completions: LLMCompletionTypedMessages[] | undefined;
};

export function ProxyMessageRunFooter(props: Props) {
  const { run, completions } = props;

  const contextWindowInformation = useMemo(() => {
    return getContextWindowInformation(completions);
  }, [completions]);

  const price = useMemo(() => {
    if (!run?.cost_usd) {
      return '-';
    }
    return formatFractionalCurrency(run?.cost_usd);
  }, [run]);

  const duration = useMemo(() => {
    if (!run?.duration_seconds) {
      return '-';
    }
    return `${run?.duration_seconds.toFixed(1)}s`;
  }, [run]);

  return (
    <div className='grid grid-cols-[repeat(auto-fit,minmax(max(140px,33%),1fr))] [&>*]:border-gray-200 [&>*]:border-b [&>*]:border-r border-l'>
      <div className='h-10 items-center flex justify-between px-4'>
        <Money16Regular className='w-4 h-4 text-gray-500' />
        <div className='text-gray-500 text-[13px]'>{price}</div>
      </div>
      <div className='h-10 items-center flex justify-between px-4'>
        <Timer16Regular className='w-4 h-4 text-gray-500' />
        <div className='text-gray-500 text-[13px]'>{duration}</div>
      </div>
      <div className='h-10 items-center flex justify-between px-4'>
        <Window16Regular className='w-4 h-4 text-gray-500' />

        {!!contextWindowInformation ? (
          <div className='flex flex-row max-w-[80px] w-full h-full items-center'>
            <ContextWindowProgressBar contextWindowInformation={contextWindowInformation} />
          </div>
        ) : (
          <div className='text-gray-500 text-[13px]'>-</div>
        )}
      </div>
    </div>
  );
}
