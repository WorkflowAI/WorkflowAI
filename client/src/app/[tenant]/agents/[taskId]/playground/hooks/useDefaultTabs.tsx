import { nanoid } from 'nanoid';
import { useCallback, useMemo } from 'react';
import { useCompatibleAIModels } from '@/lib/hooks/useCompatibleAIModels';
import { TaskID, TaskSchemaID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';
import { MajorVersion } from '@/types/workflowAI/models';
import { Tab } from './utils';

// If there are no tabs in params and storage, we should use the default ones. To do that we need two things:
// 1. There should be a newest major version
// 2. There should be compatible models for the newest major version

export function useDefaultTabs(
  tenant: TenantID | undefined,
  taskId: TaskID,
  majorVersions: MajorVersion[],
  isInitialized: boolean,
  newestSchemaId: TaskSchemaID | undefined
) {
  // We will need this major version for default tabs
  const newestMajorVersion = useMemo(() => {
    if (majorVersions.length === 0) {
      return undefined;
    }

    const sortedMajorVersions = majorVersions.sort((a, b) => b.major - a.major);
    return sortedMajorVersions[0];
  }, [majorVersions]);

  const newestMajorVersionSchemaId = useMemo(() => {
    if (!newestMajorVersion) {
      return undefined;
    }
    return `${newestMajorVersion.schema_id}` as TaskSchemaID;
  }, [newestMajorVersion]);

  const schemaId = newestMajorVersionSchemaId ?? newestSchemaId;

  // We will need those models for default tabs
  const { compatibleModels } = useCompatibleAIModels({
    tenant,
    taskId,
    taskSchemaId: schemaId,
  });

  const allDefaultTabs = useMemo(() => {
    if ((!newestMajorVersion || !compatibleModels) && !isInitialized) {
      return undefined;
    }

    const result = compatibleModels.map((model) => ({
      id: nanoid(10),
      majorVersion: newestMajorVersion,
      modelId: model.id,
      runId: undefined,
    }));

    if (result.length === 0) {
      return undefined;
    }

    return result;
  }, [newestMajorVersion, compatibleModels, isInitialized]);

  // By default we should show only three tabs, so we need only first three models
  const defaultTabs = useMemo(() => {
    if (!allDefaultTabs) {
      return undefined;
    }

    const firstThreeTabs = allDefaultTabs.slice(0, 3);
    return firstThreeTabs;
  }, [allDefaultTabs]);

  const findNewTab = useCallback(
    (tabs: Tab[] | undefined) => {
      if (!allDefaultTabs) {
        return undefined;
      }

      const filteredTabs = allDefaultTabs.filter((tab) => {
        if (!tabs) {
          return true;
        }

        return !tabs.some(
          (existingTab) =>
            existingTab.majorVersion?.major === tab.majorVersion?.major && existingTab.modelId === tab.modelId
        );
      });

      if (filteredTabs.length === 0) {
        return undefined;
      }

      return filteredTabs[0];
    },
    [allDefaultTabs]
  );

  return { defaultTabs, findNewTab };
}
