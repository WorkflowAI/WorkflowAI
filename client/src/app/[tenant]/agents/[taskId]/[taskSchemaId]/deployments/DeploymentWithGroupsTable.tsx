import { ArrowSync16Regular, Code16Regular } from '@fluentui/react-icons';
import dayjs from 'dayjs';
import { useRouter } from 'next/navigation';
import { useCallback, useMemo } from 'react';
import { PlainModelBadge } from '@/components/ModelBadge/ModelBadge';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { TaskSchemaBadgeContainer } from '@/components/TaskSchemaBadge/TaskSchemaBadgeContainer';
import { VersionRunCountContainer } from '@/components/VersionRunCountContainer';
import { TooltipButtonGroup } from '@/components/buttons/TooltipButtonGroup';
import { UserAvatar } from '@/components/ui/Avatar/UserAvatar';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { useViewRuns } from '@/components/v2/TaskRunCountBadge/useViewRuns';
import { taskApiRoute } from '@/lib/routeFormatter';
import { useOrFetchClerkUsers } from '@/store/fetchers';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { User } from '@/types/user';
import { VersionEnvironment, VersionV1 } from '@/types/workflowAI';
import { EditEnvSchemaIterationParams } from './DeployVersionModal';

const rowClassNames = 'grid grid-cols-[60px_75px_210px_1fr_125px]';

type DeploymentGroupRowProps = {
  environment: VersionEnvironment;
  version: VersionV1;
  setEnvSchemaIteration: (envSchemaIteration: EditEnvSchemaIterationParams) => void;
  tenant: TenantID;
  taskId: TaskID;
  isInDemoMode: boolean;
  usersByID: Record<string, User>;
};

function DeploymentGroupRow(props: DeploymentGroupRowProps) {
  const { environment, version, tenant, taskId, setEnvSchemaIteration, isInDemoMode, usersByID } = props;
  const router = useRouter();
  const taskSchemaId = `${version.schema_id}` as TaskSchemaID;

  const onViewCode = useCallback(() => {
    router.push(
      taskApiRoute(tenant, taskId, taskSchemaId, {
        selectedGroupIteration: version.iteration,
        selectedEnvironment: environment,
      })
    );
  }, [router, tenant, taskId, taskSchemaId, version.iteration, environment]);

  const onViewRuns = useViewRuns(taskSchemaId, version);

  const onUpdateVersion = useCallback(() => {
    if (!version.schema_id || !version.iteration) {
      return;
    }
    setEnvSchemaIteration({
      schemaId: version.schema_id.toString() as TaskSchemaID,
      environment,
      currentIteration: version.iteration.toString() ?? null,
      iteration: version.iteration.toString() ?? null,
    });
  }, [setEnvSchemaIteration, version.schema_id, environment, version.iteration]);

  const deployment = version.deployments?.[0];

  const deployedAt = useMemo(() => {
    if (!deployment?.deployed_at) {
      return '';
    }
    return dayjs(deployment.deployed_at).format('MMM D, YYYY @ h:mm A');
  }, [deployment?.deployed_at]);

  const user = useMemo(() => {
    const deployment = version.deployments?.find((deployment) => deployment.environment === environment);

    const userId = deployment?.deployed_by?.user_id;

    if (!userId) {
      return undefined;
    }

    return usersByID[userId];
  }, [version, usersByID, environment]);

  const userTooltipText = useMemo(() => {
    if (!user) {
      return 'Deployed';
    }
    return `Deployed by ${user.firstName} ${user.lastName}`;
  }, [user]);

  return (
    <TooltipButtonGroup
      items={[
        {
          icon: <ArrowSync16Regular />,
          text: 'Update Version',
          onClick: onUpdateVersion,
          disabled: isInDemoMode,
        },
        {
          icon: <Code16Regular />,
          text: 'View Code',
          onClick: onViewCode,
        },
      ]}
    >
      <TableRow className={rowClassNames}>
        <TableCell>
          <TaskSchemaBadgeContainer schemaId={`${version.schema_id}` as TaskSchemaID} />
        </TableCell>
        <TableCell>
          <TaskVersionBadgeContainer version={version} side='right' />
        </TableCell>
        <TableCell>
          <PlainModelBadge version={version} />
        </TableCell>
        <TableCell>
          <div className='flex flex-row items-center gap-2'>
            {!!user && <UserAvatar tooltipText={userTooltipText} user={user} />}
            {deployedAt}
          </div>
        </TableCell>
        <TableCell>
          <VersionRunCountContainer tenant={tenant} taskId={taskId} version_id={version.id} onClick={onViewRuns} />
        </TableCell>
      </TableRow>
    </TooltipButtonGroup>
  );
}

type DeploymentWithGroupsTableProps = {
  environment: VersionEnvironment;
  versions: VersionV1[] | undefined;
  setEnvSchemaIteration: (envSchemaIteration: EditEnvSchemaIterationParams) => void;

  tenant: TenantID;
  taskId: TaskID;
  isInDemoMode: boolean;
};

export function DeploymentWithGroupsTable(props: DeploymentWithGroupsTableProps) {
  const { environment, versions, tenant, taskId, setEnvSchemaIteration, isInDemoMode } = props;

  const userIds = useMemo(() => {
    if (!versions) {
      return [];
    }

    const result: string[] = [];
    for (const version of versions) {
      if (version.created_by?.user_id) {
        result.push(version.created_by.user_id);
      }
    }

    return result;
  }, [versions]);

  const { usersByID } = useOrFetchClerkUsers(userIds);

  return (
    <div className='p-4'>
      <Table gridMode>
        <TableHeader>
          <TableRow className={rowClassNames}>
            <TableHead>Schema</TableHead>
            <TableHead>Version</TableHead>
            <TableHead>Model</TableHead>
            <TableHead>Deployed</TableHead>
            <TableHead>Runs in last 24h</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {versions?.map((version) => (
            <DeploymentGroupRow
              key={version.id}
              version={version}
              tenant={tenant}
              taskId={taskId}
              setEnvSchemaIteration={setEnvSchemaIteration}
              environment={environment}
              isInDemoMode={isInDemoMode}
              usersByID={usersByID}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
