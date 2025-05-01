import { isEqual } from 'lodash';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocalStorage } from 'usehooks-ts';
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
  tabId: string | undefined,
  isOn: boolean = true
) {
  const storageKey = `usePlaygroundInputHistory-${tenant}-${taskId}-${taskSchemaId}-${tabId}`;

  const [internalInput, setInternalInput] = useLocalStorage<GeneralizedTaskInput | undefined>(storageKey, undefined);
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

  const historyRef = useRef(history);
  historyRef.current = history;

  const inputRef = useRef(internalInput);
  inputRef.current = internalInput;

  // At the beggining of the session, we need to set the internal input to the last input in history
  useEffect(() => {
    setHistoryIndex(undefined);
    if (historyRef.current.length > 0 && inputRef.current === undefined) {
      setInternalInput(historyRef.current[historyRef.current.length - 1].input);
    }
  }, [taskId, taskSchemaId, setInternalInput]);

  const isNewestInHistoryIdenticalToInternal = useMemo(() => {
    return isNewestInHistoryIdenticalToThisInput(internalInput, history);
  }, [internalInput, history]);

  const saveToHistory = useCallback(
    (input?: GeneralizedTaskInput) => {
      if (!isOn) {
        return;
      }

      const inputToSave = input ?? internalInput;
      const isIdenticalToNewestInHistory = isNewestInHistoryIdenticalToThisInput(inputToSave, history);

      if (!inputToSave || isIdenticalToNewestInHistory) {
        return;
      }

      addHistoryEntry(tenant, taskId, taskSchemaId, { input: inputToSave });
    },
    [internalInput, addHistoryEntry, tenant, taskId, taskSchemaId, history, isOn]
  );

  const setInput = useCallback(
    (value: GeneralizedTaskInput | undefined) => {
      setHistoryIndex(undefined);
      setInternalInput(value);
    },
    [setInternalInput]
  );

  const input = useMemo(() => {
    if (historyIndex === undefined) {
      return internalInput;
    }
    return history[historyIndex].input;
  }, [historyIndex, internalInput, history]);

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
      moveToPrevious: isPreviousAvailable ? moveToPrevious : undefined,
      moveToNext: isNextAvailable ? moveToNext : undefined,
    };
  } else {
    return {
      input: internalInput,
      setInput: setInternalInput,
      saveToHistory,
      moveToPrevious: isPreviousAvailable ? moveToPrevious : undefined,
      moveToNext: isNextAvailable ? moveToNext : undefined,
    };
  }
}
