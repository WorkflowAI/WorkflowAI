import { enableMapSet, produce } from 'immer';
import { isEmpty } from 'lodash';
import { useEffect, useRef } from 'react';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { RequestError } from '@/lib/api/client';
import { formatSemverVersion, sortEnvironmentsInOrderOfImportance } from '@/lib/versionUtils';
import { Page } from '@/types';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import {
  CreateVersionRequest,
  CreateVersionResponse,
  DeployVersionRequest,
  DeployVersionResponse,
  MajorVersion,
  Page_MajorVersion_,
  UpdateVersionNotesRequest,
  VersionEnvironment,
  VersionStat,
  VersionV1,
} from '@/types/workflowAI';
import {
  buildCreateVersionScopeKey,
  buildScopeKey,
  buildVersionScopeKey,
  taskSchemaSubPath,
  taskSubPath,
} from './utils';

enableMapSet();

export function mapMajorVersionsToVersions(majorVersions: MajorVersion[]): VersionV1[] {
  const result: VersionV1[] = [];

  majorVersions.forEach((majorVersion) => {
    majorVersion.minors.forEach((minor) => {
      const version: VersionV1 = {
        ...minor,
        semver: [majorVersion.major, minor.minor],
        created_at: majorVersion.created_at,
        properties: { ...majorVersion.properties, ...minor.properties },
        schema_id: majorVersion.schema_id,
      };
      result.push(version);
    });
  });

  result.sort((a, b) => {
    const textA = formatSemverVersion(a);
    const textB = formatSemverVersion(b);
    if (!textA || !textB) {
      return 0;
    }
    return textB.localeCompare(textA);
  });

  return result;
}

export function getDeploymentFromVersion(version: VersionV1, environment: VersionEnvironment) {
  return version.deployments?.find((deployment) => deployment.environment === environment);
}

export type VersionsPerEnvironment = Partial<Record<VersionEnvironment, VersionV1[]>>;

export function getVersionsPerEnvironment(versions: VersionV1[]): VersionsPerEnvironment | undefined {
  const result: VersionsPerEnvironment = {};

  versions.forEach((version) => {
    version.deployments?.forEach((deployment) => {
      if (!result[deployment.environment]) {
        result[deployment.environment] = [];
      }
      result[deployment.environment]?.push(version);
    });
  });

  if (isEmpty(result)) {
    return undefined;
  }

  // Sort versions within each environment by schema_id in descending order
  Object.keys(result).forEach((env) => {
    const environment = env as VersionEnvironment;
    if (result[environment]) {
      result[environment]?.sort((a, b) => {
        const deploymentA = getDeploymentFromVersion(a, environment);
        const deploymentB = getDeploymentFromVersion(b, environment);

        if (!deploymentA || !deploymentB) {
          return 0;
        }

        return new Date(deploymentB.deployed_at).getTime() - new Date(deploymentA.deployed_at).getTime();
      });
    }
  });

  return result;
}

export function getVersionIdsAndEnvironmentsDict(
  versions: VersionV1[]
): Record<string, VersionEnvironment[]> | undefined {
  const versionsPerEnvironment = getVersionsPerEnvironment(versions);
  if (!versionsPerEnvironment) {
    return undefined;
  }
  const dict: Record<string, VersionEnvironment[]> = {};

  Object.entries(versionsPerEnvironment).forEach(([environment, versions]) => {
    if (!versions) {
      return;
    }
    versions.forEach((version) => {
      if (!version.id) {
        return;
      }
      if (!dict[version.id]) {
        dict[version.id] = [];
      }
      dict[version.id].push(environment as VersionEnvironment);
    });
  });

  Object.keys(dict).forEach((key) => {
    dict[key] = sortEnvironmentsInOrderOfImportance(dict[key]);
  });

  return dict;
}

interface VersionsState {
  versionsByScope: Map<string, MajorVersion[]>;
  isLoadingVersionsByScope: Map<string, boolean>;
  isInitializedVersionsByScope: Map<string, boolean>;

  versionByScope: Map<string, VersionV1>;
  isLoadingVersionByScope: Map<string, boolean>;
  isInitializedVersionByScope: Map<string, boolean>;

  isSavingVersion: Map<string, boolean>;

  isCreatingVersion: Map<string, boolean>;
  createdVersions: Map<string, CreateVersionResponse>;
  createVersionErrors: Map<string, RequestError>;
  createVersion: (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    body: CreateVersionRequest
  ) => Promise<CreateVersionResponse>;

  createVersionInternally: (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    body: CreateVersionRequest
  ) => Promise<void>;

  saveVersion: (tenant: TenantID | undefined, taskId: TaskID, versionId: string) => Promise<CreateVersionResponse>;

  fetchVersions: (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID | undefined
  ) => Promise<void>;

  fetchVersion: (tenant: TenantID | undefined, taskId: TaskID, versionId: string) => Promise<VersionV1 | undefined>;

  favoriteVersion: (tenant: TenantID | undefined, taskId: TaskID, versionId: string) => Promise<void>;

  unfavoriteVersion: (tenant: TenantID | undefined, taskId: TaskID, versionId: string) => Promise<void>;

  updateNote: (tenant: TenantID | undefined, taskId: TaskID, versionId: string, note: string) => Promise<void>;

  deployVersion: (
    tenant: TenantID | undefined,
    taskId: TaskID,
    versionId: string,
    request: DeployVersionRequest
  ) => Promise<VersionV1 | undefined>;
}

export const useVersions = create<VersionsState>((set, get) => ({
  versionsByScope: new Map(),
  isLoadingVersionsByScope: new Map(),
  isInitializedVersionsByScope: new Map(),

  versionByScope: new Map(),
  isLoadingVersionByScope: new Map(),
  isInitializedVersionByScope: new Map(),

  isSavingVersion: new Map(),

  isCreatingVersion: new Map(),
  createdVersions: new Map(),
  createVersionErrors: new Map(),
  createVersion: async (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    body: CreateVersionRequest
  ) => {
    const response = await client.post<CreateVersionRequest, CreateVersionResponse>(
      taskSchemaSubPath(tenant, taskId, taskSchemaId, `/versions`, true),
      body
    );
    return response;
  },

  // This method differs from createVersion in the fact that it keeps the state, and that enables us to use the useOrCreateVersion hook
  createVersionInternally: async (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    body: CreateVersionRequest
  ) => {
    const scopeKey = buildCreateVersionScopeKey({
      tenant,
      taskId,
      taskSchemaId,
      body,
    });

    set(
      produce((state) => {
        state.isCreatingVersion.set(scopeKey, true);
      })
    );

    try {
      const response = await client.post<CreateVersionRequest, CreateVersionResponse>(
        taskSchemaSubPath(tenant, taskId, taskSchemaId, `/versions`, true),
        body
      );

      set(
        produce((state) => {
          state.isCreatingVersion.set(scopeKey, false);
          state.createdVersions.set(scopeKey, response);
        })
      );
    } catch (error) {
      set(
        produce((state) => {
          state.createVersionErrors.set(scopeKey, error as RequestError);
          state.isCreatingVersion.set(scopeKey, false);
        })
      );
    }
  },

  saveVersion: async (tenant, taskId, versionId) => {
    set(
      produce((state) => {
        state.isSavingVersion.set(versionId, true);
      })
    );

    const response = await client.post<Record<string, never>, CreateVersionResponse>(
      taskSubPath(tenant, taskId, `/versions/${versionId}/save`, true),
      {}
    );
    if (!!response.id) {
      await get().fetchVersion(tenant, taskId, response.id);
      await get().fetchVersions(tenant, taskId, undefined);
    }

    set(
      produce((state) => {
        state.isSavingVersion.set(versionId, false);
      })
    );
    return response;
  },

  fetchVersions: async (tenant, taskId, taskSchemaId) => {
    const scopeKey = buildScopeKey({
      tenant,
      taskId,
      taskSchemaId,
    });

    if (get().isLoadingVersionsByScope.get(scopeKey)) return;
    set(
      produce((state) => {
        state.isLoadingVersionsByScope.set(scopeKey, true);
      })
    );

    const path = taskSubPath(tenant, taskId, `/versions${taskSchemaId ? `?schema_id=${taskSchemaId}` : ''}`, true);

    try {
      const { items } = await client.get<Page_MajorVersion_>(path);

      set(
        produce((state) => {
          state.versionsByScope.set(scopeKey, items);

          if (!taskSchemaId) {
            const versionsByScopeToSave: Record<string, MajorVersion[]> = {};

            items.forEach((majorVersion) => {
              const key = buildScopeKey({
                tenant,
                taskId,
                taskSchemaId: `${majorVersion.schema_id}`,
              });

              if (versionsByScopeToSave[key]) {
                versionsByScopeToSave[key].push(majorVersion);
              } else {
                versionsByScopeToSave[key] = [majorVersion];
              }
            });

            Object.entries(versionsByScopeToSave).forEach(([key, value]) => {
              state.versionsByScope.set(key, value);
            });
          }
        })
      );
    } catch (error) {
      console.error('Failed to fetch versions', error);
    }

    set(
      produce((state) => {
        state.isLoadingVersionsByScope.set(scopeKey, false);
        state.isInitializedVersionsByScope.set(scopeKey, true);
      })
    );
  },

  fetchVersion: async (tenant, taskId, versionId) => {
    const scopeKey = buildVersionScopeKey({
      tenant,
      taskId,
      versionId,
    });

    if (get().isLoadingVersionByScope.get(scopeKey)) return;
    set(
      produce((state) => {
        state.isLoadingVersionByScope.set(scopeKey, true);
      })
    );

    const path = taskSubPath(tenant, taskId, `/versions/${versionId}`, true);

    let version: VersionV1 | undefined = undefined;
    try {
      version = await client.get<VersionV1>(path);

      set(
        produce((state) => {
          state.versionByScope.set(scopeKey, version);
        })
      );
    } catch (error) {
      console.error('Failed to fetch version', error);
    }

    set(
      produce((state) => {
        state.isLoadingVersionByScope.set(scopeKey, false);
        state.isInitializedVersionByScope.set(scopeKey, true);
      })
    );

    return version;
  },

  favoriteVersion: async (tenant, taskId, versionId) => {
    await client.post(taskSubPath(tenant, taskId, `/versions/${versionId}/favorite`, true), {});

    await get().fetchVersion(tenant, taskId, versionId);
    get().fetchVersions(tenant, taskId, undefined);
  },

  unfavoriteVersion: async (tenant, taskId, versionId) => {
    await client.del(taskSubPath(tenant, taskId, `/versions/${versionId}/favorite`, true), {});

    await get().fetchVersion(tenant, taskId, versionId);
    get().fetchVersions(tenant, taskId, undefined);
  },

  updateNote: async (tenant, taskId, versionId, notes) => {
    await client.patch<UpdateVersionNotesRequest>(taskSubPath(tenant, taskId, `/versions/${versionId}/notes`, true), {
      notes,
    });

    await get().fetchVersion(tenant, taskId, versionId);
    get().fetchVersions(tenant, taskId, undefined);
  },

  deployVersion: async (tenant, taskId, versionId, request) => {
    await client.post<DeployVersionRequest, DeployVersionResponse>(
      taskSubPath(tenant, taskId, `/versions/${versionId}/deploy`, true),
      request
    );

    const version = await get().fetchVersion(tenant, taskId, versionId);
    await get().fetchVersions(tenant, taskId, undefined);

    const versionByScope = get().versionByScope;
    versionByScope.forEach(async (candiate) => {
      if (
        candiate.schema_id !== version?.schema_id ||
        candiate.id === versionId ||
        candiate.deployments === undefined ||
        candiate.deployments?.length === 0
      ) {
        return;
      }

      await get().fetchVersion(tenant, taskId, candiate.id);
    });

    return version;
  },
}));

interface VersionsStatsState {
  versionsStatsByScope: Map<string, Map<string, VersionStat>>;
  isInitializedByScope: Map<string, boolean>;
  isLoadingByScope: Map<string, boolean>;
  fetchVersionsStats(tenant: TenantID, taskId: TaskID): Promise<void>;
}

const useVersionsStats = create<VersionsStatsState>((set, get) => ({
  versionsStatsByScope: new Map(),
  isInitializedByScope: new Map(),
  isLoadingByScope: new Map(),
  fetchVersionsStats: async (tenant, taskId) => {
    const scopeKey = buildScopeKey({ tenant, taskId });
    if (get().isLoadingByScope.get(scopeKey)) return;
    set(
      produce((state) => {
        state.isLoadingByScope.set(scopeKey, true);
      })
    );
    try {
      const { items } = await client.get<Page<VersionStat>>(taskSubPath(tenant, taskId, `/versions/stats`, true));
      set(
        produce((state) => {
          state.versionsStatsByScope.set(scopeKey, new Map(items.map((item) => [item.version_id, item])));
          state.isInitializedByScope.set(scopeKey, true);
          state.isLoadingByScope.set(scopeKey, false);
        })
      );
    } catch (error) {
      console.error('Failed to fetch versions stats', error);
      set(
        produce((state) => {
          state.isLoadingByScope.set(scopeKey, false);
        })
      );
    }
  },
}));

export function useOrFetchVersionsStats(tenant: TenantID, taskId: TaskID) {
  const scopeKey = buildScopeKey({ tenant, taskId });
  const { versionsStatsByScope, isInitializedByScope, isLoadingByScope, fetchVersionsStats } = useVersionsStats();
  const isInitialized = isInitializedByScope.get(scopeKey);
  const isLoading = isLoadingByScope.get(scopeKey);

  useEffect(() => {
    fetchVersionsStats(tenant, taskId);
  }, [fetchVersionsStats, taskId, tenant]);

  return {
    versionsStats: versionsStatsByScope.get(scopeKey),
    isInitialized,
    isLoading,
  };
}

export const useOrCreateVersion = (
  tenant: TenantID | undefined,
  taskId: TaskID,
  taskSchemaId: TaskSchemaID,
  body: CreateVersionRequest | undefined
) => {
  const scopeKey = buildCreateVersionScopeKey({
    tenant,
    taskId,
    taskSchemaId,
    body,
  });

  const createVersionInternally = useVersions((state) => state.createVersionInternally);
  const isCreatingVersion = useVersions((state) => (scopeKey ? state.isCreatingVersion.get(scopeKey) : false));
  const createdVersion = useVersions((state) => (scopeKey ? state.createdVersions.get(scopeKey) : undefined));
  const error = useVersions((state) => (scopeKey ? state.createVersionErrors.get(scopeKey) : undefined));

  const isCreatingVersionRef = useRef(isCreatingVersion);
  isCreatingVersionRef.current = isCreatingVersion;

  const wasVersionCreatedRef = useRef(false);
  wasVersionCreatedRef.current = !!createdVersion;

  useEffect(() => {
    if (!wasVersionCreatedRef.current && !isCreatingVersionRef.current && !!body) {
      createVersionInternally(tenant, taskId, taskSchemaId, body);
    }
  }, [createVersionInternally, isCreatingVersionRef, tenant, taskId, taskSchemaId, body]);

  return {
    isCreatingVersion,
    createdVersion,
    error,
  };
};
