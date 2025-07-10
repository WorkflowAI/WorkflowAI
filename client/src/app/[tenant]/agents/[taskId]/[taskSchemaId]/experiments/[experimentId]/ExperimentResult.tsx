import { Experiment } from '@/types/workflowAI/models';

type Props = {
  experiment: Experiment;
};

export function ExperimentResult(props: Props) {
  const { experiment } = props;
  return (
    <div className='flex w-full flex-col border border-gray-200 rounded-[2px] bg-white'>
      <div className='flex flex-col px-4 py-3 gap-1'>
        <div className='text-[13px] font-regular text-gray-500'>Result</div>
        <div className='text-[20px] font-regular text-gray-700'>{experiment.result}</div>
      </div>
    </div>
  );
}
