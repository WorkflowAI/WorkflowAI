import { ExperimentSummary } from '@/types/workflowAI/models';

type Props = {
  experiment: ExperimentSummary;
  onClick: (id: string) => void;
};

export function ExperimentSummaryItem(props: Props) {
  const { experiment, onClick } = props;

  return (
    <div
      className='flex w-full px-4 py-3 bg-white rounded-[2px] border border-gray-200 hover:bg-gray-50 cursor-pointer'
      onClick={() => onClick(experiment.id)}
    >
      {experiment.name}
    </div>
  );
}
