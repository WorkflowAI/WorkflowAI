import isEqual from 'lodash/isEqual';
import { useCallback, useEffect, useState } from 'react';
import { useRedirectWithParams } from '@/lib/queryString';
import { formatTaskRunIdParam } from './utils';

type Props = {
  taskRunId1: string | undefined;
  taskRunId2: string | undefined;
  taskRunId3: string | undefined;
  setPersistedTaskRunId: (index: number, taskRunId: string | undefined) => void;
};

export function useSequentialTaskRunIdUpdates(props: Props) {
  const { taskRunId1, taskRunId2, taskRunId3, setPersistedTaskRunId } = props;
  const [tempTaskRunIdParams, setTempTaskRunIdParams] = useState<Record<string, string | undefined>>({
    taskRunId1,
    taskRunId2,
    taskRunId3,
  });

  const redirectWithParams = useRedirectWithParams();

  useEffect(() => {
    if (!isEqual(tempTaskRunIdParams, { taskRunId1, taskRunId2, taskRunId3 })) {
      redirectWithParams({
        params: tempTaskRunIdParams,
        scroll: false,
      });
    }
  }, [tempTaskRunIdParams, redirectWithParams, taskRunId1, taskRunId2, taskRunId3]);

  const onTaskRunIdUpdate = useCallback(
    (index: number, runId: string | undefined) => {
      setTempTaskRunIdParams((prev) => ({
        ...prev,
        [formatTaskRunIdParam(index)]: runId,
      }));
      setPersistedTaskRunId(index, runId);
    },
    [setPersistedTaskRunId]
  );

  const onResetTaskRunIds = useCallback(() => {
    setTempTaskRunIdParams({
      taskRunId1: undefined,
      taskRunId2: undefined,
      taskRunId3: undefined,
    });
  }, []);

  return {
    onTaskRunIdUpdate,
    onResetTaskRunIds,
  };
}
