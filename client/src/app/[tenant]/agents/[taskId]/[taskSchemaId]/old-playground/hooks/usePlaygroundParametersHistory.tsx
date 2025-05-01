import { useCallback, useEffect, useMemo, useState } from 'react';
import { usePlaygroundHistoryStore } from '@/store/playgroundHistory';
import { buildScopeKey } from '@/store/utils';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';

export function usePlaygroundParametersHistory(
  tenant: TenantID | undefined,
  taskId: TaskID,
  taskSchemaId: TaskSchemaID
) {
  const { parametersHistoryByScope, addParametersHistoryEntry: addHistoryEntry } = usePlaygroundHistoryStore();

  const history = useMemo(() => {
    const scope = buildScopeKey({
      tenant,
      taskId,
      taskSchemaId,
    });
    return parametersHistoryByScope[scope] || [];
  }, [parametersHistoryByScope, tenant, taskId, taskSchemaId]);

  const [historyIndex, setHistoryIndex] = useState<number | undefined>(undefined);

  const [instructionsInternal, setInstructionsInternal] = useState<string>('');
  const [temperatureInternal, setTemperatureInternal] = useState<number>(0);

  useEffect(() => {
    setHistoryIndex(undefined);
  }, [taskId, taskSchemaId]);

  const isNewestInHistoryIdenticalToInternal = useMemo(() => {
    if (history.length === 0) {
      return false;
    }

    return (
      history[history.length - 1].instructions === instructionsInternal &&
      history[history.length - 1].temperature === temperatureInternal
    );
  }, [instructionsInternal, temperatureInternal, history]);

  const saveToHistory = useCallback(
    (externalInstructions?: string) => {
      if (isNewestInHistoryIdenticalToInternal) {
        return;
      }

      addHistoryEntry(tenant, taskId, taskSchemaId, {
        instructions: externalInstructions || instructionsInternal,
        temperature: temperatureInternal,
      });
    },
    [
      instructionsInternal,
      temperatureInternal,
      isNewestInHistoryIdenticalToInternal,
      addHistoryEntry,
      tenant,
      taskId,
      taskSchemaId,
    ]
  );

  const setInstructions = useCallback((value: string) => {
    setInstructionsInternal(value);
    setHistoryIndex(undefined);
  }, []);

  const setTemperature = useCallback(
    (value: number) => {
      setTemperatureInternal(value);
      setHistoryIndex((prev) => {
        if (prev !== undefined) {
          const instructions = history[prev].instructions;
          setInstructionsInternal(instructions);
          return undefined;
        }
        return undefined;
      });
    },
    [history]
  );

  const instructions = useMemo(() => {
    let result: string | undefined;
    if (historyIndex === undefined) {
      result = instructionsInternal;
    } else {
      result = history[historyIndex].instructions;
    }
    return result ?? '';
  }, [historyIndex, instructionsInternal, history]);

  const temperature = useMemo(() => {
    if (historyIndex === undefined) {
      return temperatureInternal;
    }
    return history[historyIndex].temperature;
  }, [historyIndex, temperatureInternal, history]);

  const isPreviousAvailable = useMemo(() => {
    if (historyIndex === undefined) {
      if (history.length === 1 && isNewestInHistoryIdenticalToInternal) {
        return false;
      }
      return history.length > 0;
    }
    return historyIndex > 0;
  }, [historyIndex, history, isNewestInHistoryIdenticalToInternal]);

  const isNextAvailable = useMemo(() => {
    if (historyIndex === undefined) {
      return false;
    }
    return historyIndex < history.length;
  }, [historyIndex, history]);

  const moveToPrevious = useCallback(() => {
    if (historyIndex === 0 || history.length === 0) {
      return;
    }

    if (isNewestInHistoryIdenticalToInternal && historyIndex === undefined) {
      setHistoryIndex(history.length - 2);
      return;
    }

    const newIndex = historyIndex ? historyIndex - 1 : history.length - 1;
    setHistoryIndex(newIndex);
  }, [historyIndex, history, isNewestInHistoryIdenticalToInternal]);

  const moveToNext = useCallback(() => {
    if (historyIndex === undefined) {
      return;
    }

    if (historyIndex > history.length - 2) {
      setHistoryIndex(undefined);
      return;
    }

    if (isNewestInHistoryIdenticalToInternal && historyIndex === history.length - 2) {
      setHistoryIndex(undefined);
      return;
    }

    const newIndex = historyIndex + 1;
    setHistoryIndex(newIndex);
  }, [historyIndex, history, isNewestInHistoryIdenticalToInternal]);

  return {
    instructions,
    temperature,
    setInstructions,
    setTemperature,
    saveToHistory,
    isPreviousAvailable,
    isNextAvailable,
    moveToPrevious,
    moveToNext,
  };
}
