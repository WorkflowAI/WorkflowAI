'use client';

import { useMemo } from 'react';
import { Loader } from '@/components/ui/Loader';
import { useOrFetchSchema, useOrFetchVersion, useOrFetchVersions } from '@/store';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { VersionEnvironment } from '@/types/workflowAI';
import { ApiContent } from './ApiContent';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  setSelectedVersionId: (newVersionId: string | undefined) => void;
  setSelectedEnvironment: (
    newSelectedEnvironment: VersionEnvironment | undefined,
    newSelectedVersionId: string | undefined
  ) => void;
  selectedVersionId: string | undefined;
  selectedEnvironment: string | undefined;
};

export function ApiContainer(props: Props) {
  const {
    tenant,
    taskId,
    setSelectedVersionId,
    setSelectedEnvironment,
    selectedVersionId: selectedVersionIdValue,
    selectedEnvironment: selectedEnvironmentValue,
  } = props;

  const { versions, versionsPerEnvironment, isInitialized: isVersionsInitialized } = useOrFetchVersions(tenant, taskId);

  const preselectedEnvironment = useMemo(() => {
    if (!!versionsPerEnvironment?.production) {
      return 'production';
    }
    if (!!versionsPerEnvironment?.staging) {
      return 'staging';
    }
    if (!!versionsPerEnvironment?.dev) {
      return 'dev';
    }
    return undefined;
  }, [versionsPerEnvironment]);

  const preselectedVersionId = useMemo(() => {
    if (!!preselectedEnvironment) {
      return versionsPerEnvironment?.[preselectedEnvironment]?.[0]?.id;
    }
    return versions[0]?.id;
  }, [preselectedEnvironment, versionsPerEnvironment, versions]);

  const selectedVersionId = selectedVersionIdValue ?? preselectedVersionId;
  const selectedEnvironment =
    (selectedEnvironmentValue as VersionEnvironment | undefined) ??
    (!selectedVersionIdValue ? preselectedEnvironment : undefined);

  const { version: selectedVersion } = useOrFetchVersion(tenant, taskId, selectedVersionId);

  const taskSchemaId = selectedVersion?.schema_id as TaskSchemaID | undefined;

  const { taskSchema } = useOrFetchSchema(tenant, taskId, taskSchemaId);

  if (!isVersionsInitialized) {
    return <Loader centered />;
  }

  if (!versions || versions.length === 0) {
    return (
      <div className='flex-1 h-full flex items-center justify-center'>
        No saved versions found - Save a version from either the playground or the run modal
      </div>
    );
  }

  if (!taskSchemaId) {
    return (
      <div className='flex-1 h-full flex items-center justify-center'>
        No AI agent schema id - Go to the playground and run the AI agent at least once
      </div>
    );
  }

  return (
    <ApiContent
      versionsPerEnvironment={versionsPerEnvironment}
      tenant={tenant}
      taskId={taskId}
      taskSchemaId={taskSchemaId}
      versions={versions}
      selectedVersionToDeployId={selectedVersionId}
      setSelectedVersionToDeploy={setSelectedVersionId}
      selectedEnvironment={selectedEnvironment}
      setSelectedEnvironment={setSelectedEnvironment}
      taskSchema={taskSchema}
      selectedVersionForAPI={selectedVersion}
    />
  );
}
