import { isEqual } from 'lodash';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { InputHistoryEntry, usePlaygroundHistoryStore } from '@/store/playgroundHistory';
import { buildScopeKey } from '@/store/utils';
import { GeneralizedTaskInput } from '@/types';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';

function isNewestInHistoryIdenticalToThisInput(input: GeneralizedTaskInput | undefined, history: InputHistoryEntry[]) {
  if (history.length === 0) {
    return false;
  }
  const previousInput = history[history.length - 1].input;

  return isEqual(previousInput, input);
}

export function usePlaygroundInputHistory(
  tenant: TenantID | undefined,
  taskId: TaskID,
  taskSchemaId: TaskSchemaID,
  generatedInput: GeneralizedTaskInput | undefined,
  setGeneratedInput: (taskInput: GeneralizedTaskInput | undefined) => void,
  isOn: boolean = true
) {
  const { inputHistoryByScope, addInputHistoryEntry: addHistoryEntry } = usePlaygroundHistoryStore();

  const history = useMemo(() => {
    const scope = buildScopeKey({
      tenant,
      taskId,
      taskSchemaId,
    });
    return inputHistoryByScope[scope] || [];
  }, [inputHistoryByScope, tenant, taskId, taskSchemaId]);

  const [historyIndex, setHistoryIndex] = useState<number | undefined>(undefined);

  useEffect(() => {
    setHistoryIndex(undefined);
  }, [taskId, taskSchemaId]);

  const isNewestInHistoryIdenticalToInternal = useMemo(() => {
    return isNewestInHistoryIdenticalToThisInput(generatedInput, history);
  }, [generatedInput, history]);

  const saveToHistory = useCallback(
    (input?: GeneralizedTaskInput) => {
      if (!isOn) {
        return;
      }

      const inputToSave = input ?? generatedInput;
      const isIdenticalToNewestInHistory = isNewestInHistoryIdenticalToThisInput(inputToSave, history);

      if (!inputToSave || isIdenticalToNewestInHistory) {
        return;
      }

      addHistoryEntry(tenant, taskId, taskSchemaId, { input: inputToSave });
    },
    [generatedInput, addHistoryEntry, tenant, taskId, taskSchemaId, history, isOn]
  );

  const setInput = useCallback(
    (value: GeneralizedTaskInput | undefined) => {
      setGeneratedInput(value);
      setHistoryIndex(undefined);
    },
    [setGeneratedInput]
  );

  const input = useMemo(() => {
    if (historyIndex === undefined) {
      return generatedInput;
    }
    return history[historyIndex].input;
  }, [historyIndex, generatedInput, history]);

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

  if (isOn) {
    return {
      input,
      setInput,
      saveToHistory,
      isPreviousAvailable,
      isNextAvailable,
      moveToPrevious,
      moveToNext,
    };
  } else {
    return {
      input: generatedInput,
      setInput: setGeneratedInput,
      saveToHistory,
      isPreviousAvailable,
      isNextAvailable,
      moveToPrevious,
      moveToNext,
    };
  }
}
