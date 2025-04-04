'use client';

import { useCallback, useMemo } from 'react';
import { useLocalStorage } from 'usehooks-ts';
import { useApiKeysModal } from '@/components/ApiKeysModal/ApiKeysModal';
import { Loader } from '@/components/ui/Loader';
import { API_URL, RUN_URL } from '@/lib/constants';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { useParsedSearchParams, useRedirectWithParams } from '@/lib/queryString';
import {
  useOrFetchApiKeys,
  useOrFetchCurrentTaskSchema,
  useOrFetchTask,
  useOrFetchTaskRuns,
  useOrFetchVersions,
} from '@/store';
import { TaskID, TaskSchemaID } from '@/types/aliases';
import { CodeLanguage } from '@/types/snippets';
import { VersionEnvironment, VersionV1 } from '@/types/workflowAI';
import { ApiContent } from './ApiContent';
import { useTaskRunWithSecondaryInput } from './utils';

const languages: CodeLanguage[] = [CodeLanguage.TYPESCRIPT, CodeLanguage.PYTHON, CodeLanguage.REST];

export function ApiContainer() {
  const { tenant, taskId } = useTaskSchemaParams();

  const [languagesForTaskIds, setLanguagesForTaskIds] = useLocalStorage<Record<TaskID, CodeLanguage>>(
    'languagesForTaskIds',
    {}
  );

  const redirectWithParams = useRedirectWithParams();

  const {
    selectedVersionId: selectedVersionIdValue,
    selectedEnvironment: selectedEnvironmentValue,
    selectedLanguage: selectedLanguageValue,
  } = useParsedSearchParams('selectedVersionId', 'selectedEnvironment', 'selectedLanguage');

  const preselectedLanguage = languagesForTaskIds[taskId] ?? CodeLanguage.TYPESCRIPT;

  const setSelectedVersionId = useCallback(
    (newVersionId: string | undefined) => {
      redirectWithParams({
        params: {
          selectedEnvironment: undefined,
          selectedVersionId: newVersionId,
          selectedKeyOption: undefined,
        },
        scroll: false,
      });
    },
    [redirectWithParams]
  );

  const { versions, versionsPerEnvironment, isInitialized: isVersionsInitialized } = useOrFetchVersions(tenant, taskId);

  const { apiKeys, isInitialized: isApiKeysInitialized } = useOrFetchApiKeys(tenant);
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

  const selectedVersion: VersionV1 | undefined = useMemo(() => {
    return versions.find((version) => {
      if (version.id === undefined) {
        return false;
      }
      return selectedVersionId === version.id;
    });
  }, [versions, selectedVersionId]);

  const setSelectedEnvironment = useCallback(
    (newSelectedEnvironment: VersionEnvironment | undefined, newSelectedVersionId: string | undefined) => {
      redirectWithParams({
        params: {
          selectedEnvironment: newSelectedEnvironment,
          selectedVersionId: newSelectedVersionId,
        },
        scroll: false,
      });
    },
    [redirectWithParams]
  );

  const taskSchemaId = selectedVersion?.schema_id as TaskSchemaID | undefined;

  const { taskSchema, isInitialized: isTaskSchemaInitialized } = useOrFetchCurrentTaskSchema(
    tenant,
    taskId,
    taskSchemaId
  );

  const { taskRuns, isInitialized: isTaskRunsInitialized } = useOrFetchTaskRuns(
    tenant,
    taskId,
    taskSchemaId,
    'limit=1&sort_by=recent'
  );

  const [taskRun, secondaryInput] = useTaskRunWithSecondaryInput(taskRuns, taskSchema);

  const { task, isInitialized: isTaskInitialized } = useOrFetchTask(tenant, taskId);

  const selectedLanguage = !selectedLanguageValue
    ? preselectedLanguage
    : (selectedLanguageValue as CodeLanguage | undefined);

  const setSelectedLanguage = useCallback(
    (language: CodeLanguage) => {
      setLanguagesForTaskIds((prev) => ({
        ...prev,
        [taskId]: language,
      }));
      redirectWithParams({
        params: {
          selectedLanguage: language,
        },
        scroll: false,
      });
    },
    [redirectWithParams, setLanguagesForTaskIds, taskId]
  );

  const apiUrl = API_URL === 'https://api.workflowai.com' ? undefined : RUN_URL;

  if (!isVersionsInitialized) {
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

  if (!isTaskSchemaInitialized || !isTaskRunsInitialized || !isTaskInitialized || !isApiKeysInitialized) {
    return <Loader centered />;
  }

  if (!task) {
    return <div className='flex-1 h-full flex items-center justify-center'>No task found</div>;
  }

  return (
    <ApiContent
      apiKeys={apiKeys}
      versionsPerEnvironment={versionsPerEnvironment}
      openApiKeysModal={openApiKeysModal}
      tenant={tenant}
      taskId={taskId}
      taskSchemaId={taskSchemaId}
      task={task}
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
    />
  );
}
