import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useLocalStorage } from 'usehooks-ts';
import { getNewestSchemaId } from '@/lib/taskUtils';
import { useOrFetchTaskSchema, useOrFetchVersions } from '@/store';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { MajorVersion, SerializableTask } from '@/types/workflowAI';
import { useBufferedParamsForTabs } from './useBufferedParamsForTabs';
import { useDefaultTabs } from './useDefaultTabs';
import { Tab } from './utils';

export function useTabs(tenant: TenantID | undefined, taskId: TaskID, task: SerializableTask | undefined) {
  const { majorVersions, versions, isInitialized } = useOrFetchVersions(tenant, taskId);

  const newestSchemaId = useMemo(() => {
    if (!task) {
      return undefined;
    }
    return getNewestSchemaId(task);
  }, [task]);

  const { taskSchema: newestSchema } = useOrFetchTaskSchema(tenant, taskId, newestSchemaId);

  const { tabs: tabsFromParams, setTabs: setTabsFromParams } = useBufferedParamsForTabs(
    majorVersions.length > 0 ? majorVersions : undefined
  );
  const tabsFromParamsRef = useRef(tabsFromParams);
  tabsFromParamsRef.current = tabsFromParams;

  // We will need those models for default tabs
  const { defaultTabs, findNewTab } = useDefaultTabs(tenant, taskId, majorVersions, isInitialized, newestSchemaId);

  const [tabsFromStorage, setTabsFromStorage] = useLocalStorage<Tab[] | undefined>(
    `useTabs-${tenant}-${taskId}`,
    undefined
  );

  // Step 1: If there are set tabs in the params, they are the new selected ones for the tabs and we should save them to the storage
  useEffect(() => {
    if (!!tabsFromParams && tabsFromParams.length > 0) {
      setTabsFromStorage(tabsFromParams);
    }
  }, [tabsFromParams, setTabsFromStorage]);

  useEffect(() => {
    // Step 2: If there are tabs in params it means that the redirect should not be done. It happened already or versions were selected in url.
    if (!!tabsFromParams && tabsFromParams.length > 0) {
      return;
    }

    // Step 3: If there are no tabs in params, we should redirect to the tabs in the storage
    if (!!tabsFromStorage && tabsFromStorage.length > 0) {
      setTabsFromParams(tabsFromStorage);
      return;
    }

    // Step 4: If there are no tabs in params and storage, we should use the default ones. To do that we need two things:
    if (!!defaultTabs && defaultTabs.length > 0) {
      setTabsFromParams(defaultTabs);
      return;
    }
  }, [tabsFromParams, tabsFromStorage, setTabsFromStorage, setTabsFromParams, defaultTabs]);

  const onCloseTab = useCallback(
    (id: string) => {
      const tabs = tabsFromParamsRef.current;

      if (!tabs) {
        return;
      }

      const newTabs = tabs.filter((tab) => tab.id !== id);
      setTabsFromParams(newTabs?.length > 0 ? newTabs : undefined);
    },
    [setTabsFromParams]
  );

  const onAddTab = useCallback(() => {
    const tabs = tabsFromParamsRef.current;

    const newTab = findNewTab(tabs);
    if (!newTab) {
      return;
    }

    setTabsFromParams([...(tabs || []), newTab]);
  }, [findNewTab, setTabsFromParams]);

  const onSelectMajorVersion = useCallback(
    (id: string, majorVersion: MajorVersion) => {
      const tabs = tabsFromParamsRef.current;

      if (!tabs) {
        return;
      }

      const newTabs = [...tabs];

      const index = newTabs.findIndex((tab) => tab.id === id);
      if (index === -1) {
        return;
      }

      newTabs[index] = {
        ...newTabs[index],
        majorVersion,
        runId: undefined,
      };
      setTabsFromParams(newTabs);
    },
    [setTabsFromParams]
  );

  const onSelectModel = useCallback(
    (id: string, model: string) => {
      const tabs = tabsFromParamsRef.current;

      if (!tabs) {
        return;
      }

      const newTabs = [...tabs];

      const index = newTabs.findIndex((tab) => tab.id === id);
      if (index === -1) {
        return;
      }

      newTabs[index] = {
        ...newTabs[index],
        modelId: model,
        runId: undefined,
      };
      setTabsFromParams(newTabs);
    },
    [setTabsFromParams]
  );

  const onSelectRun = useCallback(
    (id: string, runId: string | undefined) => {
      const tabs = tabsFromParamsRef.current;

      if (!tabs) {
        return;
      }

      const newTabs = [...tabs];

      const index = newTabs.findIndex((tab) => tab.id === id);
      if (index === -1) {
        return;
      }

      newTabs[index] = {
        ...newTabs[index],
        runId,
      };
      setTabsFromParams(newTabs);
    },
    [setTabsFromParams]
  );

  return {
    tabs: tabsFromParams,
    majorVersions,
    versions,
    newestSchema,
    onCloseTab,
    onAddTab,
    onSelectMajorVersion,
    onSelectModel,
    onSelectRun,
  };
}
