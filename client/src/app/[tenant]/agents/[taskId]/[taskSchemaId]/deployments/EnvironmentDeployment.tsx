import { ContractUpRight16Regular } from '@fluentui/react-icons';
import { capitalize } from 'lodash';
import { useCallback } from 'react';
import { EnvironmentIcon } from '@/components/icons/EnvironmentIcon';
import { Button } from '@/components/ui/Button';
import { TaskID, TaskSchemaID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';
import { VersionEnvironment, VersionV1 } from '@/types/workflowAI';
import { EditEnvSchemaIterationParams } from './DeployVersionModal';
import { DeploymentNoGroupContent } from './DeploymentNoGroupContent';
import { DeploymentWithGroupsTable } from './DeploymentWithGroupsTable';

type EnvironmentDeploymentProps = {
  environment: VersionEnvironment;
  versions: VersionV1[] | undefined;
  setEnvSchemaIteration: (envSchemaIteration: EditEnvSchemaIterationParams) => void;
  tenant: TenantID;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  isInDemoMode: boolean;
};

export function EnvironmentDeployment(props: EnvironmentDeploymentProps) {
  const { environment, versions, tenant, taskId, setEnvSchemaIteration, taskSchemaId, isInDemoMode } = props;
  const deploymentsCount = versions?.length ?? 0;

  const onDeploy = useCallback(() => {
    if (!environment) {
      return;
    }

    const newVersion = versions?.find((version) => {
      if (`${version.schema_id}` !== taskSchemaId) {
        return false;
      }

      if (!version.deployments) {
        return false;
      }

      const deployment = version.deployments.find((deployment) => deployment.environment === environment);

      return deployment;
    });

    setEnvSchemaIteration({
      environment: environment,
      schemaId: taskSchemaId,
      currentIteration: (newVersion?.iteration.toString() as string) ?? null,
      iteration: (newVersion?.iteration.toString() as string) ?? null,
    });
  }, [setEnvSchemaIteration, environment, taskSchemaId, versions]);

  return (
    <div className='w-full border-b border-dashed'>
      <div className='flex flex-row items-center justify-between px-4 py-2.5 border-b border-dashed'>
        <div className='flex items-center gap-2 text-gray-500'>
          <EnvironmentIcon environment={environment} className='w-5 h-5' />
          <div className='text-gray-700 font-semibold capitalize'>{environment}</div>
          {deploymentsCount > 1 && <div>{`Deployments across ${deploymentsCount} schemas`}</div>}
        </div>

        {deploymentsCount > 0 && (
          <Button
            icon={<ContractUpRight16Regular />}
            variant='newDesign'
            onClick={onDeploy}
            size='sm'
            disabled={isInDemoMode}
          >
            Deploy {capitalize(environment)} Version
          </Button>
        )}
      </div>
      {deploymentsCount === 0 ? (
        <DeploymentNoGroupContent environment={environment} onDeploy={onDeploy} isInDemoMode={isInDemoMode} />
      ) : (
        <DeploymentWithGroupsTable
          environment={environment}
          versions={versions}
          tenant={tenant}
          taskId={taskId}
          setEnvSchemaIteration={setEnvSchemaIteration}
          isInDemoMode={isInDemoMode}
        />
      )}
    </div>
  );
}
