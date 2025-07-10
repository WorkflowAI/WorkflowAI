import { AnnotationComponent } from '@/app/[tenant]/components/Annotations/AnnotationComponent';
import { TaskOutputViewer } from '@/components/ObjectViewer/TaskOutputViewer';
import { Experiment } from '@/types/workflowAI/models';

type Props = {
  experiment: Experiment;
};

export function ExperimentOutputSchema(props: Props) {
  const { experiment } = props;

  return (
    <div className='flex w-full flex-col gap-4'>
      <div className='text-[20px] font-semibold text-gray-900'>Output Schema</div>
      <div className='flex flex-col px-4 py-3 border border-gray-200 rounded-[2px] bg-white text-[12px] text-gray-700'>
        <TaskOutputViewer
          textColor='text-gray-500'
          value={undefined}
          schema={experiment?.output_schema ?? undefined}
          defs={experiment?.output_schema?.$defs}
          showDescriptionExamples='all'
          showTypes={true}
          showDescriptionPopover={false}
          supportAnnotations={true}
        />
      </div>
      <AnnotationComponent />
    </div>
  );
}
