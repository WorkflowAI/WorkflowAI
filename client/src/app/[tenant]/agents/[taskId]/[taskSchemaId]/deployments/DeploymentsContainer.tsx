'use client';

import { useCallback, useMemo, useState } from 'react';
import { useEnvDeploy } from '@/components/DeployIterationModal/DeployVersionModal';
import { Button } from '@/components/ui/Button';
import { PageContainer } from '@/components/v2/PageContainer';
import { PROVIDER_KEYS_MODAL_OPEN, useQueryParamModal } from '@/lib/globalModal';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { formatSemverVersion } from '@/lib/versionUtils';
import { useOrFetchOrganizationSettings, useOrFetchTask, useOrFetchVersions } from '@/store';
import { useOrganizationSettings } from '@/store/organization_settings';
import { useVersions } from '@/store/versions';
import { TaskSchemaID } from '@/types/aliases';
import { VersionV1 } from '@/types/workflowAI';
import { DeployVersionModal, EditEnvSchemaIterationParams } from './DeployVersionModal';
import { EnvironmentDeployment } from './EnvironmentDeployment';

export function DeploymentsContainer() {
  const { tenant, taskId, taskSchemaId } = useTaskSchemaParams();
  const { task, isInitialized: isTaskInitialized } = useOrFetchTask(tenant, taskId);

  const {
    versions,

    versionsPerEnvironment,
    isInitialized: isVersionsInitialized,
  } = useOrFetchVersions(tenant, taskId);

  const fetchVersions = useVersions((state) => state.fetchVersions);

  const [envSchemaIteration, setEnvSchemaIteration] = useState<EditEnvSchemaIterationParams | undefined>();

  const onCloseEnvSchemaIteration = useCallback(() => setEnvSchemaIteration(undefined), [setEnvSchemaIteration]);

  const favoriteVersions = useMemo(() => versions.filter((version) => version.is_favorite), [versions]);

  const deployVersionToEnv = useEnvDeploy(
    tenant,
    taskId,
    envSchemaIteration?.schemaId?.toString() as TaskSchemaID | undefined
  );

  const onDeploy = useCallback(async () => {
    if (!envSchemaIteration) {
      return;
    }

    const version = versions.find((version) => version.iteration.toString() === envSchemaIteration.iteration);

    const versionId = version?.id;
    const versionText = formatSemverVersion(version);

    if (!versionId) {
      return;
    }

    await deployVersionToEnv(envSchemaIteration.environment, versionId, versionText);

    await fetchVersions(tenant, taskId, undefined);
    onCloseEnvSchemaIteration();
  }, [deployVersionToEnv, envSchemaIteration, fetchVersions, tenant, taskId, onCloseEnvSchemaIteration, versions]);

  const onIterationChange = useCallback(
    (iteration: string) => {
      if (!envSchemaIteration) {
        return;
      }
      setEnvSchemaIteration({ ...envSchemaIteration, iteration });
    },
    [setEnvSchemaIteration, envSchemaIteration]
  );

  const { openModal: openProviderKeysModal } = useQueryParamModal(PROVIDER_KEYS_MODAL_OPEN);

  const handleOpenProviderKeysModal = useCallback(() => {
    openProviderKeysModal();
  }, [openProviderKeysModal]);

  const { isInDemoMode } = useDemoMode();

  const commonProps = {
    tenant,
    taskId,
    setEnvSchemaIteration,
    taskSchemaId,
    versionsPerEnvironment,
    isInDemoMode,
  };

  return (
    <PageContainer
      name='Deployments'
      task={task}
      showSchema={false}
      isInitialized={isTaskInitialized && isVersionsInitialized}
      documentationLink='https://docs.workflowai.com/features/deployments'
      rightBarChildren={
        <div className='flex flex-row items-center gap-2 font-lato'>
          <Button variant='newDesign' onClick={handleOpenProviderKeysModal} className='min-h-8' disabled={isInDemoMode}>
            Manage Provider Keys
          </Button>
        </div>
      }
    >
      <div className='flex flex-col h-full w-full overflow-y-auto font-lato'>
        <EnvironmentDeployment
          environment={'production'}
          versions={versionsPerEnvironment?.production}
          {...commonProps}
        />
        <EnvironmentDeployment environment={'staging'} versions={versionsPerEnvironment?.staging} {...commonProps} />
        <EnvironmentDeployment environment={'dev'} versions={versionsPerEnvironment?.dev} {...commonProps} />
      </div>
      <DeployVersionModal
        envSchemaIteration={envSchemaIteration}
        setEnvSchemaIteration={setEnvSchemaIteration}
        onClose={onCloseEnvSchemaIteration}
        onDeploy={onDeploy}
        onIterationChange={onIterationChange}
        isInitialized={isVersionsInitialized}
        favoriteVersions={favoriteVersions}
        allVersions={versions}
        tenant={tenant}
        taskId={taskId}
      />
    </PageContainer>
  );
}
