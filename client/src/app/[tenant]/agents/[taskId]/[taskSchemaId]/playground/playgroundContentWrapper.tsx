'use client';

import { useRef } from 'react';
import { Loader } from '@/components/ui/Loader';
import {
  useCompatibleAIModels,
  useTaskSchemaMode,
} from '@/lib/hooks/useCompatibleAIModels';
import {
  useOrFetchLatestTaskRun,
  useOrFetchTask,
  useOrFetchVersions,
} from '@/store';
import { useOrFetchCurrentTaskSchema } from '@/store';
import { PlaygroundContent, PlaygroundContentProps } from './playgroundContent';

export function PlaygroundContentWrapper(props: PlaygroundContentProps) {
  const { taskId, taskSchemaId, tenant } = props;

  const { taskSchema } = useOrFetchCurrentTaskSchema(
    tenant,
    taskId,
    taskSchemaId
  );

  const fileFormat = useTaskSchemaMode(taskSchema);
  const {
    compatibleModels,
    allModels,
    isInitialized: areModelsInitialized,
  } = useCompatibleAIModels({ tenant, taskId, taskSchemaId });
  const { task } = useOrFetchTask(tenant, taskId);

  const { versions, isInitialized: areVersionsInitialized } =
    useOrFetchVersions(tenant, taskId, taskSchemaId);

  const { taskRun: latestTaskRun, isInitialized: isLatestTaskRunInitialized } =
    useOrFetchLatestTaskRun(tenant, taskId, taskSchemaId);

  const playgroundOutputRef = useRef<HTMLDivElement>(null);

  if (
    !taskSchema ||
    !areModelsInitialized ||
    !isLatestTaskRunInitialized ||
    !task ||
    !areVersionsInitialized
  ) {
    return <Loader centered />;
  }

  return (
    <PlaygroundContent
      {...props}
      taskSchema={taskSchema}
      aiModels={compatibleModels}
      allAIModels={allModels}
      versions={versions}
      fileFormat={fileFormat}
      latestTaskRun={latestTaskRun}
      playgroundOutputRef={playgroundOutputRef}
    />
  );
}
