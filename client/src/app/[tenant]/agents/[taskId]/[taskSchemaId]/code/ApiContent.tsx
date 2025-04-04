'use client';

import { useCallback } from 'react';
import { Button } from '@/components/ui/Button';
import { PageContainer } from '@/components/v2/PageContainer';
import { PageSection } from '@/components/v2/PageSection';
import { useAuthUI } from '@/lib/AuthContext';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { TaskSchemaParams } from '@/lib/routeFormatter';
import { VersionsPerEnvironment } from '@/store/versions';
import { CodeLanguage } from '@/types/snippets';
import { TaskSchemaResponseWithSchema } from '@/types/task';
import { TaskRun } from '@/types/task_run';
import { APIKeyResponse, SerializableTask, VersionEnvironment, VersionV1 } from '@/types/workflowAI';
import { APILanguageSelection } from './APILanguageSelection';
import { ApiContentSectionItem } from './ApiContentSectionItem';
import { ApiTabsContent } from './ApiTabsContent';
import { DeployBanner } from './DeployBanner';
import { ManageApiKeysButton } from './ManageApiKeyButton';
import { VersionPopover } from './VersionPopover';

export enum APIKeyOption {
  Own = 'Own',
  WorkflowAI = 'WorkflowAI',
}

type ApiContentProps = TaskSchemaParams & {
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
  task: SerializableTask;
  taskRun: TaskRun | undefined;
  taskSchema: TaskSchemaResponseWithSchema | undefined;
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
    task,
    taskId,
    taskRun,
    taskSchema,
    taskSchemaId,
    tenant,
  } = props;

  const { openOrganizationProfile: rawOpenOrganizationProfile } = useAuthUI();

  const openOrganizationProfile = useCallback(() => {
    if (!rawOpenOrganizationProfile) {
      return;
    }

    rawOpenOrganizationProfile();
    // We want to support showing the memeber tab as the first one with the invite user selected, Clerk is not providing a way to do this directly
    // so we need to do this by using hacks
    setTimeout(() => {
      const membersButton = document.querySelector('.cl-navbarButton__members');
      if (membersButton instanceof HTMLElement) {
        membersButton.click();
        setTimeout(() => {
          const inviteButton = document.querySelector('.cl-membersPageInviteButton');
          if (inviteButton instanceof HTMLElement) {
            inviteButton.click();
          }
        }, 0);
      }
    }, 100);
  }, [rawOpenOrganizationProfile]);

  const { isInDemoMode } = useDemoMode();

  const inviteTeamButton = (
    <Button variant='newDesign' onClick={openOrganizationProfile} disabled={isInDemoMode}>
      Invite Team
    </Button>
  );

  const manageKeysButton = (
    <ManageApiKeysButton apiKeys={apiKeys} openApiKeysModal={openApiKeysModal} disabled={isInDemoMode} />
  );

  return (
    <PageContainer
      task={task}
      isInitialized
      name='Code'
      showCopyLink={true}
      extraButton={inviteTeamButton}
      showSchema={false}
      documentationLink='https://docs.workflowai.com/features/code'
    >
      <div className='flex flex-row h-full w-full'>
        <div className='h-full border-r border-dashed border-gray-200 w-[308px] flex-shrink-0'>
          <PageSection title='Settings' />
          <div className='flex flex-col gap-4 px-4 py-3'>
            <ApiContentSectionItem title='Language'>
              <APILanguageSelection
                languages={languages}
                selectedLanguage={selectedLanguage}
                setSelectedLanguage={setSelectedLanguage}
              />
            </ApiContentSectionItem>
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

        <div className='flex flex-col h-full flex-1 overflow-hidden'>
          <DeployBanner version={selectedVersionForAPI} />
          <ApiTabsContent
            tenant={tenant}
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
        </div>
      </div>
    </PageContainer>
  );
}
