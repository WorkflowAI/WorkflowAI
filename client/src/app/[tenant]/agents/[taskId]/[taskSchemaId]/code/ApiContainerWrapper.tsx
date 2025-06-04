'use client';

import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { PageContainer } from '@/components/v2/PageContainer';
import { useAuthUI } from '@/lib/AuthContext';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { useParsedSearchParams, useRedirectWithParams } from '@/lib/queryString';
import { useOrFetchTask } from '@/store/fetchers';
import { CodeLanguage } from '@/types/snippets';
import { VersionEnvironment } from '@/types/workflowAI';
import { ApiContainer } from './ApiContainer';

export function ApiContainerWrapper() {
  const { tenant, taskId } = useTaskSchemaParams();
  const redirectWithParams = useRedirectWithParams();

  const {
    selectedVersionId: selectedVersionIdParam,
    selectedEnvironment: selectedEnvironmentParam,
    selectedLanguage: selectedLanguageParam,
    selectedIntegrationId: selectedIntegrationIdParam,
  } = useParsedSearchParams('selectedVersionId', 'selectedEnvironment', 'selectedLanguage', 'selectedIntegrationId');

  const [selectedVersionId, setSelectedVersionIdToState] = useState<string | undefined>(selectedVersionIdParam);
  const [selectedEnvironment, setSelectedEnvironmentToState] = useState<string | undefined>(selectedEnvironmentParam);
  const [selectedLanguage, setSelectedLanguageToState] = useState<string | undefined>(selectedLanguageParam);
  const [selectedIntegrationId, setSelectedIntegrationIdToState] = useState<string | undefined>(
    selectedIntegrationIdParam
  );

  useEffect(() => {
    setSelectedVersionIdToState(selectedVersionIdParam);
    setSelectedEnvironmentToState(selectedEnvironmentParam);
    setSelectedLanguageToState(selectedLanguageParam);
    setSelectedIntegrationIdToState(selectedIntegrationIdParam);
  }, [selectedVersionIdParam, selectedEnvironmentParam, selectedLanguageParam, selectedIntegrationIdParam]);

  const setSelectedVersionId = useCallback(
    (newVersionId: string | undefined) => {
      setSelectedEnvironmentToState(undefined);
      setSelectedVersionIdToState(newVersionId);

      redirectWithParams({
        params: {
          selectedEnvironment: undefined,
          selectedVersionId: newVersionId,
        },
        scroll: false,
      });
    },
    [redirectWithParams]
  );

  const setSelectedEnvironment = useCallback(
    (newSelectedEnvironment: VersionEnvironment | undefined, newSelectedVersionId: string | undefined) => {
      setSelectedVersionIdToState(newSelectedVersionId);
      setSelectedEnvironmentToState(newSelectedEnvironment);

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

  const setSelectedLanguage = useCallback(
    (language: CodeLanguage) => {
      setSelectedLanguageToState(language);

      redirectWithParams({
        params: {
          selectedLanguage: language,
        },
        scroll: false,
      });
    },
    [redirectWithParams]
  );

  const setSelectedIntegrationId = useCallback(
    (integrationId: string | undefined) => {
      setSelectedIntegrationIdToState(integrationId);

      redirectWithParams({
        params: {
          selectedIntegrationId: integrationId,
        },
        scroll: false,
      });
    },
    [redirectWithParams]
  );

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

  const { task } = useOrFetchTask(tenant, taskId);

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
      <ApiContainer
        tenant={tenant}
        taskId={taskId}
        setSelectedVersionId={setSelectedVersionId}
        setSelectedEnvironment={setSelectedEnvironment}
        setSelectedLanguage={setSelectedLanguage}
        setSelectedIntegrationId={setSelectedIntegrationId}
        selectedVersionId={selectedVersionId}
        selectedEnvironment={selectedEnvironment}
        selectedLanguage={selectedLanguage}
        selectedIntegrationId={selectedIntegrationId}
      />
    </PageContainer>
  );
}
