'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocalStorage } from 'usehooks-ts';
import { useApiKeysModal } from '@/components/ApiKeysModal/ApiKeysModal';
import { Loader } from '@/components/ui/Loader';
import { API_URL, RUN_URL } from '@/lib/constants';
import {
  useOrFetchApiKeys,
  useOrFetchSchema,
  useOrFetchTaskRuns,
  useOrFetchVersion,
  useOrFetchVersions,
} from '@/store';
import { useOrFetchIntegrations } from '@/store/integrations';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { CodeLanguage } from '@/types/snippets';
import { VersionEnvironment } from '@/types/workflowAI';
import { checkSchemaForProxy } from '../proxy-playground/utils';
import { ApiContent } from './ApiContent';
import { useTaskRunWithSecondaryInput } from './utils';

const languages: CodeLanguage[] = [CodeLanguage.TYPESCRIPT, CodeLanguage.PYTHON, CodeLanguage.REST];

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  setSelectedVersionId: (newVersionId: string | undefined) => void;
  setSelectedEnvironment: (
    newSelectedEnvironment: VersionEnvironment | undefined,
    newSelectedVersionId: string | undefined
  ) => void;
  setSelectedLanguage: (language: CodeLanguage) => void;
  setSelectedIntegrationId: (integrationId: string | undefined) => void;
  selectedVersionId: string | undefined;
  selectedEnvironment: string | undefined;
  selectedLanguage: string | undefined;
  selectedIntegrationId: string | undefined;
};

export function ApiContainer(props: Props) {
  const {
    tenant,
    taskId,
    setSelectedVersionId,
    setSelectedEnvironment,
    setSelectedLanguage: setSelectedLanguageFromProps,
    setSelectedIntegrationId: setSelectedIntegrationIdFromProps,
    selectedVersionId: selectedVersionIdValue,
    selectedEnvironment: selectedEnvironmentValue,
    selectedLanguage: selectedLanguageValue,
    selectedIntegrationId: selectedIntegrationIdValue,
  } = props;

  const [languagesForTaskIds, setLanguagesForTaskIds] = useLocalStorage<Record<TaskID, CodeLanguage>>(
    'languagesForTaskIds',
    {}
  );

  const [selectedIntegrationIdForTaskIds, setSelectedIntegrationIdForTaskIds] = useLocalStorage<Record<TaskID, string>>(
    'selectedIntegrationIdForTaskIds',
    {}
  );

  const { integrations } = useOrFetchIntegrations();

  const preselectedLanguage = languagesForTaskIds[taskId] ?? CodeLanguage.TYPESCRIPT;

  const preselectedIntegrationId = selectedIntegrationIdForTaskIds[taskId] ?? integrations?.[0]?.id;

  const { versions, versionsPerEnvironment, isInitialized: isVersionsInitialized } = useOrFetchVersions(tenant, taskId);

  const { apiKeys } = useOrFetchApiKeys(tenant);
  const { openModal: openApiKeysModal } = useApiKeysModal();

  const preselectedEnvironment = useMemo(() => {
    if (!!versionsPerEnvironment?.production) {
      return 'production';
    }
    if (!!versionsPerEnvironment?.staging) {
      return 'staging';
    }
    if (!!versionsPerEnvironment?.dev) {
      return 'dev';
    }
    return undefined;
  }, [versionsPerEnvironment]);

  const preselectedVersionId = useMemo(() => {
    if (!!preselectedEnvironment) {
      return versionsPerEnvironment?.[preselectedEnvironment]?.[0]?.id;
    }
    return versions[0]?.id;
  }, [preselectedEnvironment, versionsPerEnvironment, versions]);

  const selectedVersionId = selectedVersionIdValue ?? preselectedVersionId;
  const selectedEnvironment =
    (selectedEnvironmentValue as VersionEnvironment | undefined) ??
    (!selectedVersionIdValue ? preselectedEnvironment : undefined);

  const { version: selectedVersion } = useOrFetchVersion(tenant, taskId, selectedVersionId);

  const taskSchemaId = selectedVersion?.schema_id as TaskSchemaID | undefined;

  const { taskSchema } = useOrFetchSchema(tenant, taskId, taskSchemaId);

  const [isProxy, setIsProxy] = useState(false);
  useEffect(() => {
    if (!taskSchema) {
      return;
    }
    setIsProxy(checkSchemaForProxy(taskSchema));
  }, [taskSchema]);

  const { taskRuns } = useOrFetchTaskRuns(tenant, taskId, taskSchemaId, 'limit=1&sort_by=recent');

  const [taskRun, secondaryInput] = useTaskRunWithSecondaryInput(taskRuns, taskSchema);

  const selectedLanguage = !selectedLanguageValue
    ? preselectedLanguage
    : (selectedLanguageValue as CodeLanguage | undefined);

  const selectedIntegrationId = selectedIntegrationIdValue ?? preselectedIntegrationId;

  const setSelectedLanguage = useCallback(
    (language: CodeLanguage) => {
      setLanguagesForTaskIds((prev) => ({
        ...prev,
        [taskId]: language,
      }));

      setSelectedLanguageFromProps(language);
    },
    [setLanguagesForTaskIds, setSelectedLanguageFromProps, taskId]
  );

  const setSelectedIntegrationId = useCallback(
    (integrationId: string | undefined) => {
      setSelectedIntegrationIdForTaskIds((prev) => ({
        ...prev,
        [taskId]: integrationId,
      }));

      setSelectedIntegrationIdFromProps(integrationId);
    },
    [setSelectedIntegrationIdForTaskIds, setSelectedIntegrationIdFromProps, taskId]
  );

  const apiUrl = API_URL === 'https://api.workflowai.com' ? undefined : RUN_URL;

  if (!isVersionsInitialized || !taskSchemaId) {
    return <Loader centered />;
  }

  if (!versions || versions.length === 0) {
    return (
      <div className='flex-1 h-full flex items-center justify-center'>
        No saved versions found - Save a version from either the playground or the run modal
      </div>
    );
  }

  if (!taskSchemaId) {
    return (
      <div className='flex-1 h-full flex items-center justify-center'>
        No AI agent schema id - Got to the playground and run the AI agent at least once
      </div>
    );
  }

  return (
    <ApiContent
      apiKeys={apiKeys}
      versionsPerEnvironment={versionsPerEnvironment}
      openApiKeysModal={openApiKeysModal}
      tenant={tenant}
      taskId={taskId}
      taskSchemaId={taskSchemaId}
      selectedLanguage={selectedLanguage}
      setSelectedLanguage={setSelectedLanguage}
      languages={languages}
      versions={versions}
      selectedVersionToDeployId={selectedVersionId}
      setSelectedVersionToDeploy={setSelectedVersionId}
      selectedEnvironment={selectedEnvironment}
      setSelectedEnvironment={setSelectedEnvironment}
      taskSchema={taskSchema}
      taskRun={taskRun}
      apiUrl={apiUrl}
      secondaryInput={secondaryInput}
      selectedVersionForAPI={selectedVersion}
      selectedIntegrationId={selectedIntegrationId}
      setSelectedIntegrationId={setSelectedIntegrationId}
      integrations={integrations}
      isProxy={isProxy}
    />
  );
}
