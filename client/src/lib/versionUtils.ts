import { getVersionIdsAndEnvironmentsDict } from '@/store/versions';
import { MajorVersion, VersionV1 } from '@/types/workflowAI';
import { VersionEnvironment } from '@/types/workflowAI';

export const ENVIRONMENT_IMPORTANCE: { [key in VersionEnvironment]: number } = {
  production: 0,
  staging: 1,
  dev: 2,
};

export function getEnvironmentShorthandName(environment: VersionEnvironment | undefined): string | undefined {
  if (!environment) {
    return undefined;
  }

  switch (environment) {
    case 'dev':
      return 'Dev';
    case 'staging':
      return 'Staging';
    case 'production':
      return 'Prod';
    default:
      return 'Unknown';
  }
}

export function getEnvironmentCapitalizedFullName(environment: VersionEnvironment | undefined): string | undefined {
  if (!environment) {
    return undefined;
  }

  switch (environment) {
    case 'dev':
      return 'Development';
    case 'staging':
      return 'Staging';
    case 'production':
      return 'Production';
    default:
      return 'Unknown';
  }
}

export function formatSemverVersion(
  version: VersionV1 | undefined,
  hideMinorVersion: boolean = false
): string | undefined {
  if (!version) {
    return undefined;
  }
  if (!version.semver) {
    return undefined;
  }
  const semver = version.semver as [number, number];
  if (hideMinorVersion) {
    return `${semver[0]}`;
  }
  return `${semver[0]}.${semver[1]}`;
}

export function sortVersions(versions: VersionV1[]): VersionV1[] {
  return versions.sort((lhs, rhs) => {
    const lhsVersion = Number(formatSemverVersion(lhs));
    const rhsVersion = Number(formatSemverVersion(rhs));
    if (!lhsVersion || !rhsVersion) {
      return 0;
    }
    return rhsVersion - lhsVersion;
  });
}

export function sortVersionsByEnvironment(
  versions: VersionV1[],
  versionIdsAndEnvironmentsDict: Record<string, VersionEnvironment[]> | undefined
): VersionV1[] {
  let enviromentVersions: VersionV1[] = [];
  let nonEnviromentVersions: VersionV1[] = [];

  versions.forEach((version) => {
    if (!version.id) {
      return;
    }

    if (versionIdsAndEnvironmentsDict?.[version.id]) {
      enviromentVersions.push(version);
    } else {
      nonEnviromentVersions.push(version);
    }
  });

  enviromentVersions = enviromentVersions.sort((lhs, rhs) => {
    if (!lhs.id || !rhs.id) {
      return 0;
    }

    const lhsMostImportantEnvironment = versionIdsAndEnvironmentsDict?.[lhs.id]?.[0];
    const rhsMostImportantEnvironment = versionIdsAndEnvironmentsDict?.[rhs.id]?.[0];

    if (!lhsMostImportantEnvironment || !rhsMostImportantEnvironment) {
      return 0;
    }

    return ENVIRONMENT_IMPORTANCE[lhsMostImportantEnvironment] - ENVIRONMENT_IMPORTANCE[rhsMostImportantEnvironment];
  });

  nonEnviromentVersions = sortVersions(nonEnviromentVersions);

  return [...enviromentVersions, ...nonEnviromentVersions];
}

export function sortVersionsTakingIntoAccountEnvironments(versions: VersionV1[]): VersionV1[] {
  const versionIdsAndEnvironmentsDict = getVersionIdsAndEnvironmentsDict(versions);
  return sortVersionsByEnvironment(versions, versionIdsAndEnvironmentsDict);
}

export function sortEnvironmentsInOrderOfImportance(environments: VersionEnvironment[]): VersionEnvironment[] {
  return environments.sort((lhs, rhs) => ENVIRONMENT_IMPORTANCE[lhs] - ENVIRONMENT_IMPORTANCE[rhs]);
}

export function environmentsForVersion(version: VersionV1 | undefined): VersionEnvironment[] | undefined {
  if (!version) {
    return undefined;
  }
  const environments: VersionEnvironment[] = [];
  version.deployments?.forEach((deployment) => {
    environments.push(deployment.environment);
  });
  return sortEnvironmentsInOrderOfImportance(environments);
}

export function isVersionSaved(version: VersionV1): boolean {
  if (!version.semver) {
    return false;
  }
  return version.semver.length > 0;
}

export function getVersionsDictionary(versions: VersionV1[]) {
  return versions.reduce(
    (acc, version) => {
      if (version.id === undefined) return acc;
      acc[version.id] = version;
      return acc;
    },
    {} as Record<string, VersionV1>
  );
}

export function getEnvironmentsForMajorVersion(majorVersion: MajorVersion): VersionEnvironment[] | undefined {
  const allDeployments = majorVersion.minors.flatMap((minorVersion) => minorVersion.deployments ?? []);

  const environments = allDeployments
    .map((deployment) => deployment.environment)
    .filter((env): env is VersionEnvironment => env !== undefined);

  const uniqueEnvironments = [...new Set(environments)];

  return uniqueEnvironments.length > 0 ? sortEnvironmentsInOrderOfImportance(uniqueEnvironments) : undefined;
}

export function getReasoningForVersion(version: VersionV1): string | undefined {
  if (version.properties.reasoning_effort !== undefined && version.properties.reasoning_effort !== null) {
    return version.properties.reasoning_effort;
  }
  if (version.properties.reasoning_budget !== undefined && version.properties.reasoning_budget !== null) {
    return version.properties.reasoning_budget.toString();
  }
  return undefined;
}
