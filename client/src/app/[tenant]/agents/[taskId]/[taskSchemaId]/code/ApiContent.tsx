'use client';

import { useMemo } from 'react';
import { IntegrationCombobox } from '@/components/NewTaskModal/Import/IntegrationCombobox';
import { PageSection } from '@/components/v2/PageSection';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { VersionsPerEnvironment } from '@/store/versions';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { CodeLanguage } from '@/types/snippets';
import { TaskSchemaResponseWithSchema } from '@/types/task';
import { TaskRun } from '@/types/task_run';
import { APIKeyResponse, Integration, VersionEnvironment, VersionV1 } from '@/types/workflowAI';
import { checkVersionForProxy } from '../proxy-playground/utils';
import { APILanguageSelection } from './APILanguageSelection';
import { ApiContentSectionItem } from './ApiContentSectionItem';
import { ApiTabsContent } from './ApiTabsContent';
import { DeployBanner } from './DeployBanner';
import { ManageApiKeysButton } from './ManageApiKeyButton';
import { VersionPopover } from './VersionPopover';
import { ProxyApiTabsContent } from './proxy/ProxyApiTabsContent';

export enum APIKeyOption {
  Own = 'Own',
  WorkflowAI = 'WorkflowAI',
}

type ApiContentProps = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  apiKeys: APIKeyResponse[];
  versionsPerEnvironment: VersionsPerEnvironment | undefined;
  apiUrl: string | undefined;
  versions: VersionV1[];
  languages: CodeLanguage[];
  openApiKeysModal: () => void;
  secondaryInput: Record<string, unknown> | undefined;
  selectedEnvironment: VersionEnvironment | undefined;
  selectedVersionForAPI: VersionV1 | undefined;
  selectedVersionToDeployId: string | undefined;
  selectedLanguage: CodeLanguage | undefined;
  setSelectedEnvironment: (environment: VersionEnvironment | undefined, versionId: string | undefined) => void;
  setSelectedVersionToDeploy: (newVersionId: string | undefined) => void;
  setSelectedLanguage: (language: CodeLanguage) => void;
  taskRun: TaskRun | undefined;
  taskSchema: TaskSchemaResponseWithSchema | undefined;
  selectedIntegrationId: string | undefined;
  setSelectedIntegrationId: (integrationId: string | undefined) => void;
  integrations: Integration[] | undefined;
};

export function ApiContent(props: ApiContentProps) {
  const {
    apiKeys,
    versionsPerEnvironment,
    apiUrl,
    versions,
    languages,
    openApiKeysModal,
    secondaryInput,
    selectedEnvironment,
    selectedVersionForAPI,
    selectedVersionToDeployId,
    selectedLanguage,
    setSelectedEnvironment,
    setSelectedVersionToDeploy,
    setSelectedLanguage,
    taskId,
    taskRun,
    taskSchema,
    taskSchemaId,
    tenant,
    selectedIntegrationId,
    setSelectedIntegrationId,
    integrations,
  } = props;

  const isProxy = useMemo(() => {
    return checkVersionForProxy(selectedVersionForAPI);
  }, [selectedVersionForAPI]);

  const { isInDemoMode } = useDemoMode();

  const manageKeysButton = (
    <ManageApiKeysButton apiKeys={apiKeys} openApiKeysModal={openApiKeysModal} disabled={isInDemoMode} />
  );

  return (
    <div className='flex flex-row h-full w-full overflow-hidden'>
      <div className='h-full border-r border-dashed border-gray-200 w-[308px] flex-shrink-0'>
        <PageSection title='Settings' />
        <div className='flex flex-col gap-4 px-4 py-3'>
          {isProxy ? (
            <ApiContentSectionItem title='Integration'>
              <IntegrationCombobox
                integrations={integrations}
                integrationId={selectedIntegrationId}
                setIntegrationId={setSelectedIntegrationId}
                className='border-gray-300 text-[12px] py-[3px]'
                entryClassName='text-[12px]'
              />
            </ApiContentSectionItem>
          ) : (
            <ApiContentSectionItem title='Language'>
              <APILanguageSelection
                languages={languages}
                selectedLanguage={selectedLanguage}
                setSelectedLanguage={setSelectedLanguage}
              />
            </ApiContentSectionItem>
          )}

          <ApiContentSectionItem title='Version'>
            <VersionPopover
              versions={versions}
              versionsPerEnvironment={versionsPerEnvironment}
              selectedVersionId={selectedVersionToDeployId}
              setSelectedVersionId={setSelectedVersionToDeploy}
              selectedEnvironment={selectedEnvironment}
              setSelectedEnvironment={setSelectedEnvironment}
            />
          </ApiContentSectionItem>
          <ApiContentSectionItem title='Secret Keys'>{manageKeysButton}</ApiContentSectionItem>
        </div>
      </div>

      <div className='flex flex-col h-full w-[calc(100%-308px)] overflow-hidden'>
        <DeployBanner version={selectedVersionForAPI} isEnvironmentShown={selectedEnvironment !== undefined} />
        {isProxy ? (
          <ProxyApiTabsContent
            tenant={tenant}
            taskId={taskId}
            taskSchemaId={taskSchemaId}
            versionId={selectedVersionForAPI?.id}
            integrationId={selectedIntegrationId}
            integrations={integrations}
          />
        ) : (
          <ApiTabsContent
            tenant={tenant ?? ('_' as TenantID)}
            taskId={taskId}
            taskSchemaId={taskSchemaId}
            taskSchema={taskSchema}
            taskRun={taskRun}
            version={selectedVersionForAPI}
            environment={selectedEnvironment}
            language={selectedLanguage}
            apiUrl={apiUrl}
            secondaryInput={secondaryInput}
          />
        )}
      </div>
    </div>
  );
}
