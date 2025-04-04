import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { displayErrorToaster, displaySuccessToaster } from '@/components/ui/Sonner';
import { DEPLOY_ITERATION_MODAL_OPEN, useQueryParamModal } from '@/lib/globalModal';
import { useIsAllowed } from '@/lib/hooks/useIsAllowed';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { useParsedSearchParams } from '@/lib/queryString';
import { taskApiRoute } from '@/lib/routeFormatter';
import { formatSemverVersion } from '@/lib/versionUtils';
import { useOrFetchOrganizationSettings, useOrFetchVersions } from '@/store';
import { useReviewBenchmark } from '@/store/task_review_benchmark';
import { VersionsPerEnvironment, useVersions } from '@/store/versions';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { VersionEnvironment } from '@/types/workflowAI';
import { useFindProviderConfigID } from '../ProviderKeysModal/useFindProviderConfigID';
import { DeployVersionConfirmModal } from './DeployVersionConfirmModal';
import { DeployVersionContent } from './DeployVersionContent';

export function useEnvDeploy(tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID | undefined) {
  const deployVersion = useVersions((state) => state.deployVersion);

  const router = useRouter();

  const deployGroupToEnv = useCallback(
    async (
      environment: VersionEnvironment,
      versionId: string,
      versionText: string | undefined,
      iteration: number | string | undefined | null,
      providerConfigID: string | undefined | null,
      redirectToCodeAfterDeploy?: boolean
    ) => {
      if (!taskSchemaId || !iteration) {
        return;
      }
      try {
        await deployVersion(tenant, taskId, taskSchemaId, versionId, iteration, {
          environment,
          provider_config_id: providerConfigID,
        });

        if (redirectToCodeAfterDeploy) {
          router.push(
            taskApiRoute(tenant, taskId, taskSchemaId, {
              selectedVersionId: versionId,
              selectedEnvironment: environment,
            })
          );
        }
        displaySuccessToaster(
          <span>
            {`Version ${versionText} successfully deployed to ${environment}`}
            <br />
            <Link
              href={taskApiRoute(tenant, taskId, taskSchemaId, {
                selectedVersionId: versionId,
                selectedEnvironment: environment,
              })}
              className='underline cursor-pointer'
              onClick={(e) => e.stopPropagation()}
            >
              View Code
            </Link>
          </span>
        );
      } catch (e: unknown) {
        displayErrorToaster('Failed to deploy');
      }
    },
    [deployVersion, tenant, taskId, taskSchemaId, router]
  );

  return deployGroupToEnv;
}

type NewTaskModalQueryParams = {
  deployVersionId: string | undefined;
  deploySchemaId: TaskSchemaID | undefined;
  redirectToCodeAfterDeploy: 'true' | undefined;
};

const searchParams: (keyof NewTaskModalQueryParams)[] = [
  'deployVersionId',
  'deploySchemaId',
  'redirectToCodeAfterDeploy',
];

export function useDeployVersionModal() {
  const { open, openModal, closeModal } = useQueryParamModal<NewTaskModalQueryParams>(
    DEPLOY_ITERATION_MODAL_OPEN,
    searchParams
  );

  const onDeployToClick = useCallback(
    (versionId: string | undefined, schemaId?: TaskSchemaID, redirectToCodeAfterDeploy?: boolean) => {
      if (versionId === undefined) {
        return;
      }
      openModal({
        deployVersionId: versionId,
        deploySchemaId: schemaId,
        redirectToCodeAfterDeploy: !!redirectToCodeAfterDeploy ? 'true' : undefined,
      });
    },
    [openModal]
  );

  return { open, openModal, closeModal, onDeployToClick };
}

export function DeployVersionModal() {
  const { tenant, taskId, taskSchemaId: paramsTaskSchemaId } = useTaskSchemaParams();
  const { open, closeModal: onClose } = useDeployVersionModal();

  const {
    deployVersionId: currentVersionId,
    deploySchemaId,
    redirectToCodeAfterDeploy: useDeployVersionModalText,
  } = useParsedSearchParams('deployVersionId', 'deploySchemaId', 'redirectToCodeAfterDeploy');

  const redirectToCodeAfterDeploy = useDeployVersionModalText === 'true';

  const taskSchemaId = (deploySchemaId as TaskSchemaID) ?? paramsTaskSchemaId;

  const {
    versions,
    isInitialized,
    versionsPerEnvironment: originalVersionsPerEnvironment,
  } = useOrFetchVersions(tenant, taskId, taskSchemaId);

  const { checkIfAllowed } = useIsAllowed();

  useEffect(() => {
    if (open && !checkIfAllowed()) {
      onClose();
    }
  }, [open, checkIfAllowed, onClose]);

  const currentVersion = useMemo(
    () => versions.find((version) => version.id === currentVersionId),
    [versions, currentVersionId]
  );

  const currentIteration = currentVersion?.iteration;

  const [versionsPerEnvironment, setVersionsPerEnvironment] = useState<VersionsPerEnvironment>();

  useEffect(() => {
    setVersionsPerEnvironment(originalVersionsPerEnvironment);
  }, [originalVersionsPerEnvironment, open]);

  const updateBenchmark = useReviewBenchmark((state) => state.updateBenchmark);

  const [showConfirmModal, setShowConfirmModal] = useState(false);

  const onDeployToggle = useCallback(
    (environment: VersionEnvironment) => {
      const newVersionsPerEnvironment = {
        ...versionsPerEnvironment,
        [environment]:
          versionsPerEnvironment?.[environment]?.[0]?.id === currentVersion?.id ? undefined : [currentVersion],
      };
      setVersionsPerEnvironment(newVersionsPerEnvironment);
      setShowConfirmModal(true);
    },
    [versionsPerEnvironment, currentVersion]
  );

  const onCancel = useCallback(() => {
    setVersionsPerEnvironment(originalVersionsPerEnvironment);
    setShowConfirmModal(false);
  }, [originalVersionsPerEnvironment]);

  const { organizationSettings } = useOrFetchOrganizationSettings();

  useEffect(() => {
    if (!open) {
      setShowConfirmModal(false);
    }
  }, [open]);

  const { providerConfigID: settingsProviderConfigID } = useFindProviderConfigID({
    tenant,
    taskId,
    taskSchemaId,
    providerSettings: organizationSettings?.providers,
    model: currentVersion?.model,
  });

  const deployVersionToEnv = useEnvDeploy(tenant, taskId, taskSchemaId);

  const versionText = formatSemverVersion(currentVersion);

  const handleDeploy = useCallback(async () => {
    const promises: Promise<void>[] = [];

    const providerConfigID = settingsProviderConfigID;

    const taskIterationsToAddToBenchmarks: Set<number> = new Set();
    const environmentValues: VersionEnvironment[] = ['dev', 'staging', 'production'];

    environmentValues.forEach((environment) => {
      const currentTaskIteration = versionsPerEnvironment?.[environment]?.[0]?.iteration;
      const originalTaskIteration = originalVersionsPerEnvironment?.[environment]?.[0]?.iteration;

      if (
        !!currentIteration &&
        !!currentVersionId &&
        !!currentTaskIteration &&
        currentTaskIteration !== originalTaskIteration
      ) {
        promises.push(
          deployVersionToEnv(
            environment,
            currentVersionId,
            versionText,
            currentIteration,
            providerConfigID,
            redirectToCodeAfterDeploy
          )
        );
        taskIterationsToAddToBenchmarks.add(currentIteration);
      }
    });

    await Promise.all(promises);

    if (taskIterationsToAddToBenchmarks.size > 0) {
      await updateBenchmark(tenant, taskId, taskSchemaId, Array.from(taskIterationsToAddToBenchmarks), []);
    }

    onClose();
  }, [
    deployVersionToEnv,
    versionsPerEnvironment,
    originalVersionsPerEnvironment,
    currentIteration,
    currentVersionId,
    onClose,
    settingsProviderConfigID,
    updateBenchmark,
    tenant,
    taskId,
    taskSchemaId,
    versionText,
    redirectToCodeAfterDeploy,
  ]);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className='p-0 max-w-[800px] w-auto overflow-hidden bg-custom-gradient-1'>
        <DeployVersionContent
          version={currentVersion}
          onClose={onClose}
          isInitialized={isInitialized}
          versionsPerEnvironment={versionsPerEnvironment}
          originalVersionsPerEnvironment={originalVersionsPerEnvironment}
          onDeploy={onDeployToggle}
        />
        <DeployVersionConfirmModal
          showConfirmModal={showConfirmModal}
          versionBadgeText={formatSemverVersion(currentVersion)}
          closeModal={onCancel}
          onConfirm={handleDeploy}
        />
      </DialogContent>
    </Dialog>
  );
}
