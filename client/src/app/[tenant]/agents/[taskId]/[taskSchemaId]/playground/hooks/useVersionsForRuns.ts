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
  hiddenModelColumns: number[] | undefined;
};

export function useVersionsForTaskRunners(props: Props) {
  const { tenant, taskId, taskRunners, hiddenModelColumns } = props;

  const { version: versionRunOne } = useOrFetchVersion(
    tenant,
    taskId,
    hiddenModelColumns?.includes(0) ? undefined : taskRunners[0].data?.group.id
  );

  const { version: versionRunTwo } = useOrFetchVersion(
    tenant,
    taskId,
    hiddenModelColumns?.includes(1) ? undefined : taskRunners[1].data?.group.id
  );

  const { version: versionRunThree } = useOrFetchVersion(
    tenant,
    taskId,
    hiddenModelColumns?.includes(2) ? undefined : taskRunners[2].data?.group.id
  );

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

  return { versionsForRuns, showSaveAllVersions: !areAllVersionsForTaskRunsSaved, onSaveAllVersions };
}
