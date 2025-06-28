import { getSearchParamsFromHistory } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/hooks/useProxyHistory';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { QueryParam, stringifyQueryParams } from './queryString';

export const PATHS = {
  SIGNIN: '/sign-in',
  SIGNUP: '/sign-up',
  SIGNUP_REDIRECT: '/sign-up-redirect',
  ORG_SELECTION: '/organization/select',
  ORG_CREATE: '/organization/create',
};

export const TENANT_PLACEHOLDER = '_';

export enum SearchFieldParam {
  FieldNames = 'field_name',
  Operators = 'operator',
  Values = 'value',
}

export type Params = Record<string, QueryParam>;

export type TaskParams = {
  taskId: TaskID;
};

export type TaskSchemaParams = TaskParams & {
  tenant: TenantID;
  taskSchemaId: TaskSchemaID;
};

export type TaskRunParams = TaskSchemaParams & {
  taskRunId: string;
};

export function landingRoute(params?: Params) {
  return `/${stringifyQueryParams(params)}`;
}

export function signInRoute(params?: Params) {
  return `${PATHS.SIGNIN}${stringifyQueryParams(params)}`;
}

export function signUpRoute(params?: Params) {
  return `${PATHS.SIGNUP}${stringifyQueryParams(params)}`;
}

export function signUpRedirectRoute(redirectUrl?: string) {
  return `${PATHS.SIGNUP_REDIRECT}${stringifyQueryParams({ redirectUrl })}`;
}

export function tasksRoute(tenant: TenantID, params?: Params) {
  return `/${decodeURIComponent(tenant)}/agents${stringifyQueryParams(params)}`;
}

export const taskRoute = (tenant: TenantID | undefined, taskId: TaskID, params?: Params) =>
  `/${decodeURIComponent(tenant ?? TENANT_PLACEHOLDER)}/agents/${taskId}${stringifyQueryParams(params)}`;

export const taskSchemaRoute = (
  tenant: TenantID | undefined,
  taskId: TaskID,
  taskSchemaId: TaskSchemaID,
  params?: Params
) => `${taskRoute(tenant, taskId)}/${taskSchemaId}${stringifyQueryParams(params)}`;

export function playgroundFromHistoryRouteBuilder(tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID) {
  return taskSchemaRoute(tenant, taskId, taskSchemaId, getSearchParamsFromHistory(tenant, taskId, taskSchemaId));
}

export const taskSchemasRoute = (tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID) =>
  `${taskSchemaRoute(tenant, taskId, taskSchemaId)}/schemas`;

export const taskBenchmarksRoute = (tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID) =>
  `${taskSchemaRoute(tenant, taskId, taskSchemaId)}/benchmarks`;

export const taskCostRoute = (tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID) =>
  `${taskSchemaRoute(tenant, taskId, taskSchemaId)}/cost`;

export const taskBenchmarkInProgressRoute = (
  tenant: TenantID | undefined,
  taskId: TaskID,
  taskSchemaId: TaskSchemaID,
  mode: string,
  params?: Params
) => `${taskSchemaRoute(tenant, taskId, taskSchemaId)}/benchmarks/${mode}/inprogress/${stringifyQueryParams(params)}`;

export const taskBenchmarkAddVersionsRoute = (
  tenant: TenantID,
  taskId: TaskID,
  taskSchemaId: TaskSchemaID,
  mode: string
) => `${taskSchemaRoute(tenant, taskId, taskSchemaId)}/benchmarks/${mode}/addversions`;

export const taskVersionsRoute = (tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID, params?: Params) =>
  `${taskSchemaRoute(tenant, taskId, taskSchemaId)}/versions${stringifyQueryParams(params)}`;

export const taskRunsRoute = (tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID, params?: Params) =>
  `${taskSchemaRoute(tenant, taskId, taskSchemaId)}/runs${stringifyQueryParams(params)}`;

export const taskReviewsRoute = (tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID, params?: Params) =>
  `${taskSchemaRoute(tenant, taskId, taskSchemaId)}/reviews${stringifyQueryParams(params)}`;

export const taskSideBySideRoute = (tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID, params?: Params) =>
  `${taskSchemaRoute(tenant, taskId, taskSchemaId)}/side-by-side${stringifyQueryParams(params)}`;

export const taskFeedbackRoute = (tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID, params?: Params) =>
  `${taskSchemaRoute(tenant, taskId, taskSchemaId)}/feedback${stringifyQueryParams(params)}`;

export const taskApiRoute = (tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID, params?: Params) =>
  `${taskSchemaRoute(tenant, taskId, taskSchemaId)}/code${stringifyQueryParams(params)}`;

export const taskDeploymentsRoute = (tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID, params?: Params) =>
  `${taskSchemaRoute(tenant, taskId, taskSchemaId)}/deployments${stringifyQueryParams(params)}`;

export const taskSampleRoute = (tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID, taskSampleId: string) =>
  `${taskSchemaRoute(tenant, taskId, taskSchemaId)}/examples/${taskSampleId}`;

export function taskRunRoute(tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID, taskRunId: string) {
  return `/${decodeURIComponent(tenant)}/agents/${taskId}/${taskSchemaId}/runs?runId=${taskRunId}`;
}

export function replaceTenant(url: string, urlTenant: string, tenant: string) {
  let parsedURL: URL;
  try {
    parsedURL = new URL(url);
  } catch (error) {
    const pathParts = url.split('/');
    if (pathParts[1] === urlTenant) {
      pathParts[1] = tenant;
    }
    return pathParts.join('/');
  }

  const pathParts = parsedURL.pathname.split('/');
  if (pathParts[1] === urlTenant) {
    pathParts[1] = tenant;
  }
  parsedURL.pathname = pathParts.join('/');
  return parsedURL.toString();
}

export function replaceTaskSchemaId(url: string, taskSchemaId: TaskSchemaID) {
  const pathParts = url.split('/');
  pathParts[4] = taskSchemaId;
  return pathParts.join('/');
}

export function replaceTaskId(url: string, taskId: TaskID, taskSchemaId?: TaskSchemaID) {
  const pathParts = url.split('/');
  pathParts[3] = taskId;
  if (taskSchemaId) {
    pathParts[4] = taskSchemaId;
  }
  return pathParts.join('/');
}

/**
 * A WebSite URL that will always be supported and that redirects to the actual run.
 */
export function staticRunURL(tenant: TenantID | undefined, taskId: string, taskRunId: string) {
  return `${window.location.origin}/${tenant ?? '_'}/agents/${taskId}/runs/${taskRunId}`;
}
