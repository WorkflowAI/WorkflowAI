import { capitalize } from 'lodash';
import { useCallback, useMemo } from 'react';
import { SchemaSelectorContainer } from '@/app/[tenant]/components/TaskSwitcherContainer';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent, DialogHeader } from '@/components/ui/Dialog';
import { Loader } from '@/components/ui/Loader';
import { TaskVersionsListSection } from '@/components/v2/TaskVersions/TaskVersionsListSection';
import { VersionAvatarType } from '@/components/v2/TaskVersions/utils';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { VersionEnvironment, VersionV1 } from '@/types/workflowAI';

type DeployVersionModalContentProps = {
  allVersions: VersionV1[];
  favoriteVersions: VersionV1[];
  isInitialized: boolean;
  onIterationChange: (iteration: string) => void;
  selectedIteration: string | null | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID | undefined;
  tenant: TenantID;
};

function DeployVersionModalContent(props: DeployVersionModalContentProps) {
  const {
    favoriteVersions,
    allVersions,
    isInitialized,
    onIterationChange,
    selectedIteration,
    taskId,
    taskSchemaId,
    tenant,
  } = props;

  if (!isInitialized || !taskSchemaId) {
    return <Loader centered />;
  }

  const commonProps = {
    tenant,
    taskId,
    taskSchemaId,
    selectedIteration,
    onIterationChange,
  };

  return (
    <div className='flex-1 flex flex-col gap-2 overflow-y-auto'>
      <TaskVersionsListSection
        allVersions={favoriteVersions}
        versionsToShow={favoriteVersions}
        areVersionsInitialized={isInitialized}
        avatarType={VersionAvatarType.Favorited}
        {...commonProps}
      />
      <TaskVersionsListSection
        allVersions={allVersions}
        versionsToShow={allVersions}
        title='All Versions'
        areVersionsInitialized={isInitialized}
        {...commonProps}
      />
    </div>
  );
}

export type EditEnvSchemaIterationParams = {
  environment: VersionEnvironment;
  schemaId: TaskSchemaID;
  currentIteration: string | null;
  iteration: string | null;
};

type DeployVersionModalProps = {
  allVersions: VersionV1[];
  envSchemaIteration: EditEnvSchemaIterationParams | undefined;
  setEnvSchemaIteration: (envSchemaIteration: EditEnvSchemaIterationParams) => void;
  favoriteVersions: VersionV1[];
  isInitialized: boolean;
  onClose: () => void;
  onDeploy: () => Promise<void>;
  onIterationChange: (iteration: string) => void;
  taskId: TaskID;
  tenant: TenantID;
};

export function DeployVersionModal(props: DeployVersionModalProps) {
  const {
    allVersions,
    envSchemaIteration,
    setEnvSchemaIteration,
    favoriteVersions,
    isInitialized,
    onClose,
    onDeploy,
    onIterationChange,
    taskId,
    tenant,
  } = props;

  const onOpenChange = useCallback(
    (open: boolean) => {
      if (!open) {
        onClose();
      }
    },
    [onClose]
  );

  const schemaIdToUse = envSchemaIteration?.schemaId;
  const environmentToUse = envSchemaIteration?.environment;

  const filteredFavoriteVersions = useMemo(() => {
    return favoriteVersions.filter((version) => {
      // Filter by schema ID
      if (`${version.schema_id}` !== schemaIdToUse) return false;

      // Filter out already deployed version for this environment
      if (
        envSchemaIteration?.currentIteration &&
        version.iteration.toString() === envSchemaIteration.currentIteration
      ) {
        return false;
      }

      return true;
    });
  }, [favoriteVersions, schemaIdToUse, envSchemaIteration?.currentIteration]);

  const filteredAllVersions = useMemo(() => {
    return allVersions.filter((version) => {
      // Filter by schema ID
      if (`${version.schema_id}` !== schemaIdToUse) return false;

      // Filter out already deployed version for this environment
      if (
        envSchemaIteration?.currentIteration &&
        version.iteration.toString() === envSchemaIteration.currentIteration
      ) {
        return false;
      }

      return true;
    });
  }, [allVersions, schemaIdToUse, envSchemaIteration?.currentIteration]);

  const handleSchemaIdChange = useCallback(
    (schemaId: TaskSchemaID) => {
      if (!environmentToUse) {
        return;
      }

      const newVersion = allVersions.find((version) => {
        if (`${version.schema_id}` !== `${schemaId}`) {
          return false;
        }

        if (!version.deployments) {
          return false;
        }

        const deployment = version.deployments.find((deployment) => deployment.environment === environmentToUse);

        return deployment;
      });

      setEnvSchemaIteration({
        environment: environmentToUse,
        schemaId,
        currentIteration: (newVersion?.iteration.toString() as string) ?? null,
        iteration: (newVersion?.iteration.toString() as string) ?? null,
      });
    },
    [environmentToUse, allVersions, setEnvSchemaIteration]
  );

  return (
    <Dialog open={!!envSchemaIteration} onOpenChange={onOpenChange}>
      <DialogContent className='flex flex-col p-0 gap-0 max-w-[95vw] max-h-[95vh]'>
        <DialogHeader
          title={`Update ${capitalize(envSchemaIteration?.environment)} Version for Schema #${schemaIdToUse}`}
          onClose={onClose}
        >
          <Button
            variant='newDesign'
            onClick={onDeploy}
            disabled={!envSchemaIteration || envSchemaIteration?.iteration === envSchemaIteration?.currentIteration}
          >
            Deploy
          </Button>
        </DialogHeader>
        {!!schemaIdToUse && (
          <div className='flex flex-row items-center gap-1 w-full border-b border-gray-200 border-dashed px-4 py-1 text-gray-700 text-[13px] font-medium'>
            <div>Select the schema you like to deploy a version for:</div>
            <SchemaSelectorContainer
              tenant={tenant}
              taskId={taskId}
              selectedSchemaId={schemaIdToUse}
              setSelectedSchemaId={handleSchemaIdChange}
              showSlash={false}
            />
          </div>
        )}
        <DeployVersionModalContent
          allVersions={filteredAllVersions}
          favoriteVersions={filteredFavoriteVersions}
          isInitialized={isInitialized}
          onIterationChange={onIterationChange}
          selectedIteration={envSchemaIteration?.iteration}
          taskId={taskId}
          taskSchemaId={schemaIdToUse}
          tenant={tenant}
        />
      </DialogContent>
    </Dialog>
  );
}
