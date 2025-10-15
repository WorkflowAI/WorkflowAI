'use client';

import { useCallback, useEffect, useState } from 'react';
import { PageContainer } from '@/components/v2/PageContainer';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { useParsedSearchParams, useRedirectWithParams } from '@/lib/queryString';
import { useOrFetchTask } from '@/store/fetchers';
import { VersionEnvironment } from '@/types/workflowAI';
import { ApiContainer } from './ApiContainer';

export function ApiContainerWrapper() {
  const { tenant, taskId } = useTaskSchemaParams();
  const redirectWithParams = useRedirectWithParams();

  const { selectedVersionId: selectedVersionIdParam, selectedEnvironment: selectedEnvironmentParam } =
    useParsedSearchParams('selectedVersionId', 'selectedEnvironment');

  const [selectedVersionId, setSelectedVersionIdToState] = useState<string | undefined>(selectedVersionIdParam);
  const [selectedEnvironment, setSelectedEnvironmentToState] = useState<string | undefined>(selectedEnvironmentParam);

  useEffect(() => {
    setSelectedVersionIdToState(selectedVersionIdParam);
    setSelectedEnvironmentToState(selectedEnvironmentParam);
  }, [selectedVersionIdParam, selectedEnvironmentParam]);

  const setSelectedVersionId = useCallback(
    (newVersionId: string | undefined) => {
      setSelectedEnvironmentToState(undefined);
      setSelectedVersionIdToState(newVersionId);

      redirectWithParams({
        params: {
          selectedEnvironment: undefined,
          selectedVersionId: newVersionId,
        },
        scroll: false,
      });
    },
    [redirectWithParams]
  );

  const setSelectedEnvironment = useCallback(
    (newSelectedEnvironment: VersionEnvironment | undefined, newSelectedVersionId: string | undefined) => {
      setSelectedVersionIdToState(newSelectedVersionId);
      setSelectedEnvironmentToState(newSelectedEnvironment);

      redirectWithParams({
        params: {
          selectedEnvironment: newSelectedEnvironment,
          selectedVersionId: newSelectedVersionId,
        },
        scroll: false,
      });
    },
    [redirectWithParams]
  );

  const { task } = useOrFetchTask(tenant, taskId);

  return (
    <PageContainer task={task} isInitialized name='Migration' showCopyLink={true} showSchema={false}>
      <ApiContainer
        tenant={tenant}
        taskId={taskId}
        setSelectedVersionId={setSelectedVersionId}
        setSelectedEnvironment={setSelectedEnvironment}
        selectedVersionId={selectedVersionId}
        selectedEnvironment={selectedEnvironment}
      />
    </PageContainer>
  );
}
