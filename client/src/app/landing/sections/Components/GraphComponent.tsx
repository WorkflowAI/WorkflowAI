import Image from 'next/image';
import { useMemo } from 'react';
import { BarChart } from '@/components/ui/BarChart';
import { cn } from '@/lib/utils';
import { useOrFetchWeeklyRuns } from '@/store/fetchers';

type Props = {
  className?: string;
  workflowUptime: number | undefined;
};

export function GraphComponent(props: Props) {
  const { className, workflowUptime } = props;

  const { weeklyRuns } = useOrFetchWeeklyRuns(6);

  const title = useMemo(() => {
    if (!weeklyRuns || weeklyRuns.length === 0) return 'We processed over 1,000,000 runs last week';
    const lastWeek = weeklyRuns[weeklyRuns.length - 1];
    return `We processed ${lastWeek.run_count} runs last week...`;
  }, [weeklyRuns]);

  const subtitle = useMemo(() => {
    if (!weeklyRuns || weeklyRuns.length === 0) return undefined;
    const lastWeek = weeklyRuns[weeklyRuns.length - 1];
    return (
      <div>
        with {lastWeek.overhead_ms}ms added latency and{' '}
        <a className='underline' href='https://status.workflowai.com/' target='_blank' rel='noopener noreferrer'>
          {workflowUptime ?? 100}% uptime
        </a>
        .
      </div>
    );
  }, [weeklyRuns, workflowUptime]);

  const costData = useMemo(() => {
    const data = weeklyRuns?.map((run) => {
      const date = new Date(run.start_of_week);
      return {
        x: `${date.getMonth() + 1}/${date.getDate()}`,
        y: run.run_count,
      };
    });

    return data;
  }, [weeklyRuns]);

  return (
    <div className={cn('flex flex-col items-center sm:gap-12 gap-8 sm:px-16 px-4 w-full max-w-[1260px]', className)}>
      <div className='flex flex-col items-center justify-center gap-4'>
        <div className='flex w-full items-center justify-center text-center text-gray-900 font-semibold sm:text-[30px] text-[24px]'>
          {title}
        </div>
        {subtitle && (
          <div className='flex w-fit items-center justify-center text-center text-gray-500 font-normal sm:text-[20px] text-[16px] whitespace-pre-wrap'>
            {subtitle}
          </div>
        )}
      </div>

      <div className='flex flex-col w-full relative'>
        <div className='absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 flex w-full h-full'>
          <Image
            src='https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration42.jpg'
            alt='graph'
            width={1168}
            height={496}
            className='w-full h-full'
          />
        </div>

        <div className='flex w-full h-full z-10 sm:px-32 sm:py-16 px-0 py-0'>
          <div className='flex w-full h-full items-center justify-center overflow-hidden sm:px-1 sm:py-3 px-0'>
            <BarChart
              data={costData ?? []}
              fractionalPart={0}
              barColor='#818CF8'
              textColor='#808896'
              showValueAboveBar={false}
              showTooltips={false}
              barRadius={2}
              tooltipLabel='Run Count'
              className='pr-3 flex w-full h-full overflow-hidden'
              hideFractionsOnYAxis={true}
              turnOffFocus={true}
              turnOffHorizontalLines={true}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
