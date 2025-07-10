import { AnnotationComponent } from '@/app/[tenant]/components/Annotations/AnnotationComponent';
import { Experiment } from '@/types/workflowAI/models';

type Props = {
  experiment: Experiment;
};

export function ExperimentPrompt(props: Props) {
  const { experiment } = props;
  return (
    <div className='flex w-full flex-col gap-4'>
      <div className='text-[20px] font-semibold text-gray-900'>Prompt</div>
      <div className='flex flex-col px-4 py-3 border border-gray-200 rounded-[2px] bg-white font-mono text-[12px] text-gray-700 whitespace-pre-wrap'>
        {experiment.prompt}
      </div>
      <AnnotationComponent />
    </div>
  );
}
