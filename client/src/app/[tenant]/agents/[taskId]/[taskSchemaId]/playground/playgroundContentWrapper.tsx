'use client';

import { useRef } from 'react';
import { Loader } from '@/components/ui/Loader';
import { useCompatibleAIModels } from '@/lib/hooks/useCompatibleAIModels';
import { useOrFetchLatestRun, useOrFetchTask, useOrFetchVersions } from '@/store';
import { useOrFetchCurrentTaskSchema } from '@/store';
import { PlaygroundContent, PlaygroundContentProps } from './playgroundContent';

export function PlaygroundContentWrapper(props: PlaygroundContentProps) {
  const { taskId, taskSchemaId, tenant } = props;

  const { taskSchema } = useOrFetchCurrentTaskSchema(tenant, taskId, taskSchemaId);

  const {
    compatibleModels,
    allModels,
    isInitialized: areModelsInitialized,
  } = useCompatibleAIModels({ tenant, taskId, taskSchemaId });

  const { task } = useOrFetchTask(tenant, taskId);

  const { versions, isInitialized: areVersionsInitialized } = useOrFetchVersions(tenant, taskId, taskSchemaId);
  const { latestRun, isInitialized: isLatestRunInitialized } = useOrFetchLatestRun(tenant, taskId, taskSchemaId);

  const playgroundOutputRef = useRef<HTMLDivElement>(null);

  if (!taskSchema || !areModelsInitialized || !isLatestRunInitialized || !task || !areVersionsInitialized) {
    return <Loader centered />;
  }

  return (
    <PlaygroundContent
      {...props}
      taskSchema={taskSchema}
      aiModels={compatibleModels}
      allAIModels={allModels}
      versions={versions}
      latestRun={latestRun}
      playgroundOutputRef={playgroundOutputRef}
    />
  );
}
