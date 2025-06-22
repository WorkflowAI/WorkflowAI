import isEqual from 'lodash/isEqual';
import { useCallback, useEffect, useState } from 'react';
import { useRedirectWithParams } from '@/lib/queryString';
import { formatRunIdParam } from './utils';

type Props = {
  runId1: string | undefined;
  runId2: string | undefined;
  runId3: string | undefined;
  setPersistedRunId: (index: number, runId: string | undefined) => void;
};

export function useSequentialRunIdUpdates(props: Props) {
  const { runId1, runId2, runId3, setPersistedRunId } = props;
  const [tempRunIdParams, setTempRunIdParams] = useState<Record<string, string | undefined>>({
    runId1,
    runId2,
    runId3,
  });

  const redirectWithParams = useRedirectWithParams();

  useEffect(() => {
    if (!isEqual(tempRunIdParams, { runId1, runId2, runId3 })) {
      redirectWithParams({
        params: tempRunIdParams,
        scroll: false,
      });
    }
  }, [tempRunIdParams, redirectWithParams, runId1, runId2, runId3]);

  const onRunIdUpdate = useCallback(
    (index: number, runId: string | undefined) => {
      setTempRunIdParams((prev) => ({
        ...prev,
        [formatRunIdParam(index)]: runId,
      }));
      setPersistedRunId(index, runId);
    },
    [setPersistedRunId]
  );

  const onResetRunIds = useCallback(() => {
    setTempRunIdParams({
      runId1: undefined,
      runId2: undefined,
      runId3: undefined,
    });
  }, []);

  return {
    onRunIdUpdate,
    onResetRunIds,
  };
}