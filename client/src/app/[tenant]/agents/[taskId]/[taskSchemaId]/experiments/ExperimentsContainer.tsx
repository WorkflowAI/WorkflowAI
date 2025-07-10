'use client';

import { usePathname } from 'next/navigation';
import { Loader } from '@/components/ui/Loader';
import { PageContainer } from '@/components/v2/PageContainer';
import { useTaskParams } from '@/lib/hooks/useTaskParams';
import { useRedirectWithParams } from '@/lib/queryString';
import { useOrFetchTask } from '@/store';
import { ExperimentSummary } from '@/types/workflowAI/models';
import { ExperimentSummaryItem } from './ExperimentSummaryItem';

export function ExperimentsContainer() {
  const { tenant, taskId } = useTaskParams();

  const redirectWithParams = useRedirectWithParams();
  const pathname = usePathname();

  const { task } = useOrFetchTask(tenant, taskId);

  const areExperimentsLoading = false;
  const experiments: ExperimentSummary[] = [
    {
      id: 'exp_01HQ2P4BNJM8K9X7YZ5R6T3V2W',
      name: 'Baseline Model Performance',
    },
    {
      id: 'exp_01HQ2P4BNKL9M8N7X6Y5T4R3Q2',
      name: 'Optimized Temperature Settings',
    },
    {
      id: 'exp_01HQ2P4BNML0N9P8Y7X6W5V4T3',
      name: 'Enhanced Prompt Engineering',
    },
    {
      id: 'exp_01HQ2P4BNNK1P0Q9Z8Y7X6W5V4',
      name: 'Fine-tuned Model Evaluation',
    },
    {
      id: 'exp_01HQ2P4BNPJ2Q1R0A9Z8Y7X6W5',
      name: 'Context Window Analysis',
    },
  ];

  const numberOfExperiments = !!experiments ? experiments.length : 0;

  const openExperiment = (experimentId: string) => {
    redirectWithParams({
      path: `${pathname}/${experimentId}`,
    });
  };

  if (areExperimentsLoading || !task) {
    return <Loader centered />;
  }

  if (numberOfExperiments < 1) {
    return (
      <PageContainer
        task={task}
        isInitialized={true}
        name='Experiments'
        showCopyLink={true}
        showBottomBorder={true}
        showSchema={false}
      >
        <div className='w-full h-full flex items-center justify-center'>Empty</div>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      task={task}
      isInitialized={true}
      name='Experiments'
      showCopyLink={true}
      showBottomBorder={true}
      showSchema={false}
    >
      <div className='flex flex-col h-full w-full overflow-hidden font-lato px-4 py-4 gap-4 justify-between'>
        <div className='flex flex-col gap-2 w-full h-full overflow-y-auto'>
          {experiments.map((experiment) => (
            <ExperimentSummaryItem
              key={experiment.id}
              experiment={experiment}
              onClick={() => openExperiment(experiment.id)}
            />
          ))}
        </div>
      </div>
    </PageContainer>
  );
}
