import { useCallback, useMemo } from 'react';
import { isVersionSaved } from '@/lib/versionUtils';
import { useOrFetchVersion } from '@/store/fetchers';
import { useVersions } from '@/store/versions';
import { TaskID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';
import { VersionV1 } from '@/types/workflowAI';
import { TaskRunner } from './useTaskRunners';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskRunners: TaskRunner[];
  instructions: string;
  temperature: number;
};

export function useVersionsForTaskRunners(props: Props) {
  const { tenant, taskId, taskRunners, instructions, temperature } = props;

  const { version: versionRunOne } = useOrFetchVersion(tenant, taskId, taskRunners[0].data?.group.id);

  const { version: versionRunTwo } = useOrFetchVersion(tenant, taskId, taskRunners[1].data?.group.id);

  const { version: versionRunThree } = useOrFetchVersion(tenant, taskId, taskRunners[2].data?.group.id);

  const versionsForRuns = useMemo(() => {
    const result: Record<string, VersionV1> = {};
    if (versionRunOne) {
      result[versionRunOne.id] = versionRunOne;
    }
    if (versionRunTwo) {
      result[versionRunTwo.id] = versionRunTwo;
    }
    if (versionRunThree) {
      result[versionRunThree.id] = versionRunThree;
    }
    return result;
  }, [versionRunOne, versionRunTwo, versionRunThree]);

  const areAllVersionsForTaskRunsSaved = useMemo(() => {
    if (!versionsForRuns) {
      return true;
    }
    return Object.values(versionsForRuns).every((version) => isVersionSaved(version));
  }, [versionsForRuns]);

  const showSaveAllVersions = useMemo(() => {
    if (areAllVersionsForTaskRunsSaved) {
      return false;
    }

    const versionsToSave = Object.values(versionsForRuns);
    const isThereVersionNotMatchingParameters = versionsToSave.some((version) => {
      return (
        version.properties.instructions?.trim().toLowerCase() !== instructions.trim().toLowerCase() ||
        version.properties.temperature !== temperature
      );
    });

    return !isThereVersionNotMatchingParameters;
  }, [areAllVersionsForTaskRunsSaved, instructions, temperature, versionsForRuns]);

  const saveVersion = useVersions((state) => state.saveVersion);

  const onSaveAllVersions = useCallback(async () => {
    const versionsToSave: VersionV1[] = [];
    Object.values(versionsForRuns).forEach((version) => {
      if (!isVersionSaved(version)) {
        versionsToSave.push(version);
      }
    });

    await Promise.all(versionsToSave.map((version) => saveVersion(tenant, taskId, version.id)));
  }, [versionsForRuns, saveVersion, tenant, taskId]);

  return { versionsForRuns, showSaveAllVersions, onSaveAllVersions };
}
