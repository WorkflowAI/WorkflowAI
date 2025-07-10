'use client';

import { usePathname } from 'next/navigation';
import { useMemo } from 'react';
import { PageContainer } from '@/components/v2/PageContainer';
import { useTaskParams } from '@/lib/hooks/useTaskParams';
import { useRedirectWithParams } from '@/lib/queryString';
import { useOrFetchSchema, useOrFetchTask } from '@/store';
import { Experiment } from '@/types/workflowAI';
import { ExperimentHeader } from './ExperimentHeader';
import { ExperimentOutputSchema } from './ExperimentOutputSchema';
import { ExperimentPrompt } from './ExperimentPrompt';
import { ExperimentResult } from './ExperimentResult';

export function ExperimentContainer() {
  const { tenant, taskId, taskSchemaId, experimentId } = useTaskParams();
  const { task } = useOrFetchTask(tenant, taskId);
  const { taskSchema } = useOrFetchSchema(tenant, taskId, taskSchemaId);

  const pathname = usePathname();
  const redirectWithParams = useRedirectWithParams();

  const goBackToExperiments = () => {
    const baseUrl = pathname.split('/experiments')[0] + '/experiments';
    redirectWithParams({
      path: baseUrl,
    });
  };

  const experiment = useMemo(() => {
    const result: Experiment = {
      id: 'exp_01HQ2P4BNJM8K9X7YZ5R6T3V2W',
      title: 'meal-planning-v2-comparison',
      result: 'Testing updated prompt with better guidelines and fiber tracking against two different models.',
      description:
        'Comparing GPT-4o-mini vs Claude-3.5-Haiku on improved meal planning agent after incorporating user feedback - evaluating breakfast appropriateness, ingredient practicality, calorie accuracy, meal variety, and fiber tracking',
      prompt: `You are an expert on animal cuteness. Consider that many animals traditionally seen as 'scary' can actually be cute (like small spiders with big eyes, or colorful creatures). Evaluate fairly without bias.

  Respond with a JSON object containing:
  - cuteness_rating: "cute" or "not cute"
  - confidence: score from 0 to 1
  - reasoning: brief explanation
  - features: list of relevant physical/behavioral traits`,
      output_schema: taskSchema?.output_schema?.json_schema ?? undefined,
    };
    return result;
  }, [taskSchema]);

  return (
    <PageContainer
      task={task}
      isInitialized={true}
      name={
        <div className='flex items-center gap-2'>
          <div className='cursor-pointer' onClick={goBackToExperiments}>
            Experiments
          </div>
          <div className='text-[14px] font-semibold text-gray-400 hidden sm:block'>/</div>
          <div>{experiment.title ?? experimentId}</div>
        </div>
      }
      showCopyLink={true}
      showBottomBorder={true}
      showSchema={false}
    >
      <div className='flex flex-col h-full w-full overflow-y-auto font-lato px-4 py-4 gap-8'>
        <ExperimentHeader experiment={experiment} />
        <ExperimentResult experiment={experiment} />
        <ExperimentPrompt experiment={experiment} />
        <ExperimentOutputSchema experiment={experiment} />
      </div>
    </PageContainer>
  );
}
