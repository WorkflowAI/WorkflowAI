import { Loader2 } from 'lucide-react';
import { useCallback, useEffect, useMemo } from 'react';
import { useLocalStorage } from 'usehooks-ts';
import { useRedirectWithParams } from '@/lib/queryString';
import { useParsedSearchParams } from '@/lib/queryString';
import { useOrFetchTaskSchema } from '@/store/fetchers';
import { TaskID, TenantID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { ModelResponse, VersionV1 } from '@/types/workflowAI';
import { TaskInputDict } from '@/types/workflowAI';
import { SideBySideTableHeader } from './SideBySideTableHeader';
import { SideBySideTableRow } from './SideBySideTableRow';
import { SideBySideTableStatsRow } from './Stats/SideBySideTableStatsRow';

type SideBySideTableProps = {
  inputs: TaskInputDict[] | undefined;
  versions: VersionV1[];
  models: ModelResponse[] | undefined;
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  page: number;
};

export function SideBySideTable(props: SideBySideTableProps) {
  const { inputs, versions, models, tenant, taskId, taskSchemaId, page } = props;

  const { selectedLeftVersionId, selectedRightVersionId, selectedRightModelId, requestedRightModelId } =
    useParsedSearchParams(
      'selectedLeftVersionId',
      'selectedRightVersionId',
      'selectedRightModelId',
      'requestedRightModelId'
    );

  const redirectWithParams = useRedirectWithParams();

  const setSelectedLeftVersionId = useCallback(
    (newLeftVersionId: string | undefined) => {
      redirectWithParams({
        params: {
          selectedLeftVersionId: newLeftVersionId,
          selectedRightVersionId: undefined,
          selectedRightModelId: undefined,
          requestedRightModelId: undefined,
        },
        scroll: false,
      });
    },
    [redirectWithParams]
  );

  const setSelectedRightVersionId = useCallback(
    (newRightVersionId: string | undefined) => {
      redirectWithParams({
        params: {
          selectedRightVersionId: newRightVersionId,
          selectedRightModelId: undefined,
        },
        scroll: false,
      });
    },
    [redirectWithParams]
  );

  const setSelectedRightModelId = useCallback(
    (newRightModelId: string | undefined) => {
      redirectWithParams({
        params: {
          selectedRightVersionId: undefined,
          selectedRightModelId: newRightModelId,
        },
        scroll: false,
      });
    },
    [redirectWithParams]
  );

  const selectedLeftVersion = versions.find((version) => version.id === selectedLeftVersionId);
  const selectedRightVersion = versions.find((version) => version.id === selectedRightVersionId);
  const selectedRightModel = models?.find((model) => model.id === selectedRightModelId);

  const { taskSchema } = useOrFetchTaskSchema(undefined, taskId, taskSchemaId);

  const deployedVersion = useMemo(() => {
    if (versions.length === 0) {
      return undefined;
    }

    const prodVersion = versions.find((version) =>
      version.deployments?.some((deployment) => deployment.environment === 'production')
    );
    if (prodVersion) return prodVersion;

    const stagingVersion = versions.find((version) =>
      version.deployments?.some((deployment) => deployment.environment === 'staging')
    );
    if (stagingVersion) return stagingVersion;

    const devVersion = versions.find((version) =>
      version.deployments?.some((deployment) => deployment.environment === 'dev')
    );
    if (devVersion) return devVersion;

    return undefined;
  }, [versions]);

  const [savedLeftVersionId, setSavedLeftVersionId] = useLocalStorage(
    `savedLeftVersionId-${taskId}-${taskSchemaId}`,
    selectedLeftVersionId
  );
  const [savedRightVersionId, setSavedRightVersionId] = useLocalStorage(
    `savedRightVersionId-${taskId}-${taskSchemaId}`,
    selectedRightVersionId
  );
  const [savedRightModelId, setSavedRightModelId] = useLocalStorage(
    `savedRightModelId-${taskId}-${taskSchemaId}`,
    selectedRightModelId
  );

  // Always save the selected Versions and Models
  useEffect(() => {
    // If left Version Id is not set, means we didn't yet set the defaults
    if (!selectedLeftVersionId) {
      return;
    }
    setSavedLeftVersionId(selectedLeftVersionId);
    setSavedRightVersionId(selectedRightVersionId);
    setSavedRightModelId(selectedRightModelId);
  }, [
    selectedLeftVersionId,
    selectedRightVersionId,
    selectedRightModelId,
    setSavedLeftVersionId,
    setSavedRightVersionId,
    setSavedRightModelId,
  ]);

  useEffect(() => {
    // We only check is selectedLeftVersionId is empty becasue that will happen only when first loading the page, it will be imposible to set it to empty later on
    if (versions.length === 0 || !!selectedLeftVersionId) {
      return;
    }

    // Default Left Version
    let defaultLeftVersionId: string | undefined = deployedVersion?.id ?? versions[0].id;

    // Default Right Version
    let defaultRightVersionId: string | undefined = undefined;

    if (deployedVersion) {
      if (defaultLeftVersionId === deployedVersion.id) {
        defaultRightVersionId = versions.length > 1 ? versions[1].id : undefined;
      } else {
        defaultRightVersionId = versions[0].id;
      }
    } else {
      defaultRightVersionId = versions.length > 1 ? versions[1].id : undefined;
    }

    // Default Right Model
    let defaultRightModelId: string | undefined = undefined;

    // Let's override default ones if there are saved ones
    defaultLeftVersionId = savedLeftVersionId ?? defaultLeftVersionId;

    // Those ids should be exclusive so if one is set in saved we want set the values for both
    if (savedRightVersionId || savedRightModelId) {
      defaultRightVersionId = savedRightVersionId;
      defaultRightModelId = savedRightModelId;
    }

    // Logic for deep linking
    let leftVersionId: string | undefined = undefined;
    let rightVersionId: string | undefined = undefined;
    let rightModelId: string | undefined = undefined;

    leftVersionId = defaultLeftVersionId;

    // We will override the selectedRightVersionId if we have a requestedRightModelId from a deeplink
    if (requestedRightModelId) {
      rightVersionId = undefined;
      rightModelId = requestedRightModelId;
    } else {
      rightVersionId = defaultRightVersionId;
      rightModelId = defaultRightModelId;
    }

    redirectWithParams({
      params: {
        selectedLeftVersionId: leftVersionId,
        selectedRightVersionId: rightVersionId,
        selectedRightModelId: rightModelId,
        requestedRightModelId: undefined,
      },
      scroll: false,
    });
  }, [
    deployedVersion,
    versions,
    selectedLeftVersionId,
    requestedRightModelId,
    redirectWithParams,
    savedLeftVersionId,
    savedRightModelId,
    savedRightVersionId,
  ]);

  return (
    <div className='flex flex-col w-full felx-1 border border-gray-200 rounded-[2px] overflow-hidden relative'>
      <SideBySideTableHeader
        versions={versions}
        models={models}
        baseVersion={selectedLeftVersion}
        selectedLeftVersionId={selectedLeftVersionId}
        setSelectedLeftVersionId={setSelectedLeftVersionId}
        selectedRightVersionId={selectedRightVersionId}
        setSelectedRightVersionId={setSelectedRightVersionId}
        selectedRightModelId={selectedRightModelId}
        setSelectedRightModelId={setSelectedRightModelId}
        page={page}
      />
      <div className='flex flex-col w-full flex-1 overflow-y-auto scrollbar-hide' id='side-by-side-table'>
        <SideBySideTableStatsRow
          tenant={tenant}
          taskId={taskId}
          taskSchemaId={taskSchemaId}
          selectedLeftVersionId={selectedLeftVersionId}
          selectedRightVersionId={selectedRightVersionId}
          selectedRightModelId={selectedRightModelId}
          inputs={inputs}
          leftVersion={selectedLeftVersion}
          rightVersion={selectedRightVersion}
        />
        {!!taskSchema && !!inputs ? (
          <>
            {inputs.map((input, index) => (
              <SideBySideTableRow
                key={index}
                input={input}
                taskSchema={taskSchema}
                selectedLeftVersion={selectedLeftVersion}
                selectedRightVersion={selectedRightVersion}
                selectedRightModel={selectedRightModel}
                tenant={tenant}
                taskId={taskId}
                taskSchemaId={taskSchemaId}
              />
            ))}
          </>
        ) : (
          <div className='flex w-full h-[200px] items-center justify-center'>
            <Loader2 className='w-8 h-8 animate-spin text-gray-200' />
          </div>
        )}
      </div>
      {!selectedLeftVersionId && (
        <div className='absolute top-[20%] left-[20%] w-[40%] items-center flex justify-center text-gray-400 text-[13px] font-medium'>
          Choose a version to compare output results...
        </div>
      )}
      {!selectedRightVersionId && !selectedRightModelId && (
        <div className='absolute top-[20%] left-[60%] w-[40%] items-center flex justify-center text-gray-400 text-[13px] font-medium'>
          Choose a version or model to compare output results...
        </div>
      )}
    </div>
  );
}
