import { Experiment } from '@/types/workflowAI/models';

type Props = {
  experiment: Experiment;
};

export function ExperimentHeader(props: Props) {
  const { experiment } = props;
  return (
    <div className='flex flex-col w-full gap-2'>
      {experiment.title && <div className='text-[30px] font-semibold text-gray-900'>{experiment.title}</div>}
      {experiment.description && <div className='text-[16px] font-regular text-gray-600'>{experiment.description}</div>}
    </div>
  );
}
