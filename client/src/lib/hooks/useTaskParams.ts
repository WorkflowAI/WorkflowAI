import { useParams } from 'next/navigation';
import { useMemo } from 'react';
import { useAuth } from '@/lib/AuthContext';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { TaskSchemaParams, tasksRoute } from '../routeFormatter';

export function useTaskParams() {
  const { tenant, taskId, taskSchemaId, taskRunId, exampleId, experimentId, mode } = useParams<{
    tenant?: TenantID;
    taskId?: TaskID;
    taskSchemaId?: TaskSchemaID;
    taskRunId?: string;
    exampleId?: string;
    experimentId?: string;
    mode?: string;
  }>();
  // Forcing a default tenant value of '_' to avoid undefined tenant values
  // tenant should always be defined here
  const decodedTenant = (tenant === undefined ? '_' : decodeURIComponent(tenant)) as TenantID;
  return {
    tenant: decodedTenant,
    taskId,
    taskSchemaId,
    taskRunId,
    exampleId,
    experimentId,
    mode,
  };
}

export function useTenantID() {
  const { tenant } = useParams<{ tenant: string }>();
  return decodeURIComponent(tenant) as TenantID;
}

export function useLoggedInTenantID() {
  const { tenantSlug } = useAuth();

  return tenantSlug;
}

export function useIsSameTenant() {
  const tenant = useTenantID();
  const loggedInTenant = useLoggedInTenantID();

  return tenant === loggedInTenant;
}

/**
 * Only use for routes that have taskId and taskSchemaId
 */
export function useTaskSchemaParams(): TaskSchemaParams {
  const { tenant, taskId, taskSchemaId } = useTaskParams();
  return {
    tenant,
    taskId: taskId as TaskID,
    taskSchemaId: taskSchemaId as TaskSchemaID,
  };
}

// Returns the default route corresponding to the authenticated user
export function useDefaultRedirectRoute(noAuthRoute: string = '/') {
  const { tenantSlug, isLoaded } = useAuth();

  return useMemo(() => {
    if (!isLoaded || !tenantSlug) {
      return noAuthRoute;
    }

    return tasksRoute(tenantSlug);
  }, [isLoaded, tenantSlug, noAuthRoute]);
}
