'use client';

import { useEffect, useMemo, useState } from 'react';
import { Loader } from '@/components/ui/Loader';
import { useCompatibleAIModels } from '@/lib/hooks/useCompatibleAIModels';
import { useOrFetchLatestRun, useOrFetchTask, useOrFetchVersions } from '@/store';
import { useOrFetchSchema } from '@/store';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { TaskSchemaResponseWithSchema } from '@/types/task';
import { ProxyPlayground } from '../proxy-playground/ProxyPlayground';
import { checkSchemaForProxy } from '../proxy-playground/utils';
import { PlaygroundContent } from './playgroundContent';

type NonProxyPlaygroundContentWrapperProps = {
  taskId: TaskID;
  tenant: TenantID | undefined;
  taskSchemaId: TaskSchemaID;
  schema: TaskSchemaResponseWithSchema;
};

export function NonProxyPlaygroundContentWrapper(props: NonProxyPlaygroundContentWrapperProps) {
  const { taskId, taskSchemaId, tenant, schema } = props;

  const { task, isInitialized: isTaskInitialized } = useOrFetchTask(tenant, taskId);

  const {
    compatibleModels,
    allModels,
    isInitialized: areModelsInitialized,
  } = useCompatibleAIModels({ tenant, taskId, taskSchemaId });

  const { versions, isInitialized: areVersionsInitialized } = useOrFetchVersions(tenant, taskId, taskSchemaId);
  const { latestRun, isInitialized: isLatestRunInitialized } = useOrFetchLatestRun(tenant, taskId, taskSchemaId);

  if (!areModelsInitialized || !isLatestRunInitialized || !task || !areVersionsInitialized) {
    return <Loader centered />;
  }

  return (
    <PlaygroundContent
      taskId={taskId}
      tenant={tenant}
      taskSchemaId={taskSchemaId}
      taskSchema={schema}
      aiModels={compatibleModels}
      allAIModels={allModels}
      versions={versions}
      latestRun={latestRun}
      task={task}
      isTaskInitialized={isTaskInitialized}
    />
  );
}

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
};

export function PlaygroundContentWrapper(props: Props) {
  const { taskId, taskSchemaId, tenant } = props;

  const { taskSchema } = useOrFetchSchema(tenant, taskId, taskSchemaId);
  const [lastTaskSchema, setLastTaskSchema] = useState<TaskSchemaResponseWithSchema | undefined>(undefined);
  useEffect(() => {
    if (taskSchema) {
      setLastTaskSchema(taskSchema);
    }
  }, [taskSchema]);

  const schema = useMemo(() => {
    return taskSchema ?? lastTaskSchema;
  }, [taskSchema, lastTaskSchema]);

  const isProxy = useMemo(() => {
    if (!schema) {
      return false;
    }
    return checkSchemaForProxy(schema);
  }, [schema]);

  if (!schema) {
    return <Loader centered />;
  }

  if (isProxy) {
    return <ProxyPlayground tenant={tenant} taskId={taskId} schemaId={`${schema.schema_id}` as TaskSchemaID} />;
  }

  return (
    <NonProxyPlaygroundContentWrapper
      tenant={tenant}
      taskId={taskId}
      taskSchemaId={`${schema.schema_id}` as TaskSchemaID}
      schema={schema}
    />
  );
}
