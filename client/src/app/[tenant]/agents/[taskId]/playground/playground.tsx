'use client';

import { Link16Regular } from '@fluentui/react-icons';
import { useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/Button';
import { PageContainer } from '@/components/v2/PageContainer';
import { useCopyCurrentUrl } from '@/lib/hooks/useCopy';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useIsMobile } from '@/lib/hooks/useIsMobile';
import { useOrFetchOrganizationSettings, useOrFetchTask } from '@/store';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { PlaygroundState } from '@/types/workflowAI';
import { PlaygroundChat } from './components/Chat/PlaygroundChat';
import { RunAgentsButton } from './components/RunAgentsButton';
import { PlaygroundAddTab } from './components/Tab/PlaygroundAddTab';
import { PlaygroundTab } from './components/Tab/PlaygroundTab';
import { useTabs } from './hooks/useTabs';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
};

export function Playground(props: Props) {
  const { tenant, taskId } = props;

  const { task, isInitialized: isTaskInitialized } = useOrFetchTask(tenant, taskId);

  const {
    tabs,
    onCloseTab,
    onAddTab,
    majorVersions,
    versions,
    onSelectMajorVersion,
    onSelectModel,
    onSelectRun,
    newestSchema,
  } = useTabs(tenant, taskId, task);

  const isMobile = useIsMobile();
  const { isInDemoMode, onDifferentTenant } = useDemoMode();
  const { noCreditsLeft } = useOrFetchOrganizationSettings();
  const copyUrl = useCopyCurrentUrl();

  const shouldShowChat = useMemo(() => {
    if (isMobile) {
      return false;
    }
    if (onDifferentTenant) {
      return false;
    }
    return true;
  }, [isMobile, onDifferentTenant]);

  // TODO: temporary constants

  // For RunAgentsButton:
  const showSaveAllVersions = false;
  const areTasksRunning = false;
  const isInputLoading = false;
  const areInstructionsLoading = false;

  const onSaveAllVersions = () => {};
  const onTryPromptClick = () => {};
  const onStopAllRuns = () => {};

  // For PlaygroundChat:
  const onShowEditSchemaModal = () => {};
  const onToolCallChangeModels = () => {};
  const onCancelChatToolCallOnPlayground = () => {};
  const onScrollToTop = () => {};
  const onScrollToPlaygroundOutput = () => {};

  const onToolCallGenerateNewInput: (instructions: string | undefined) => Promise<void> =
    useCallback(async () => {}, []);
  const onToolCallImproveInstructions: (text: string, runId: string | undefined) => Promise<void> =
    useCallback(async () => {}, []);

  const playgroundState: PlaygroundState = {
    agent_input: {},
    agent_instructions: '',
    agent_temperature: 0,
    agent_run_ids: [],
    selected_models: {
      column_1: null,
      column_2: null,
      column_3: null,
    },
  };

  const onScrollToEnd = useCallback(() => {
    const playgroundHorizontalScroll = document.getElementById('playground-horizontal-scroll');
    if (playgroundHorizontalScroll) {
      playgroundHorizontalScroll.scrollTo({
        left: playgroundHorizontalScroll.scrollWidth,
        behavior: 'smooth',
      });
    }
  }, []);

  const onAddAndScrollToNewTab = useCallback(() => {
    onAddTab();
    setTimeout(() => {
      onScrollToEnd();
    }, 100);
  }, [onAddTab, onScrollToEnd]);

  return (
    <div className='flex flex-row h-full w-full'>
      <div className='flex h-full flex-1 overflow-hidden'>
        <PageContainer
          task={task}
          isInitialized={isTaskInitialized}
          name='Playground'
          showCopyLink={false}
          showBottomBorder={true}
          showSchema={false}
          documentationLink='https://docs.workflowai.com/features/playground'
          rightBarText='Your data is not used for LLM training.'
          rightBarChildren={
            <div className='flex flex-row items-center gap-2 font-lato'>
              <Button variant='newDesign' icon={<Link16Regular />} onClick={copyUrl} className='w-9 h-9 px-0 py-0' />
              {!isMobile && (
                <RunAgentsButton
                  showSaveAllVersions={showSaveAllVersions && !noCreditsLeft && !isInDemoMode}
                  areTasksRunning={areTasksRunning}
                  inputLoading={isInputLoading}
                  areInstructionsLoading={areInstructionsLoading}
                  onSaveAllVersions={onSaveAllVersions}
                  onTryPromptClick={onTryPromptClick}
                  onStopAllRuns={onStopAllRuns}
                />
              )}
            </div>
          }
          showBorders={!isMobile}
        >
          <div className='flex flex-row px-2 overflow-x-auto bg-white min-w-full' id='playground-horizontal-scroll'>
            {tabs?.map((tab) => (
              <PlaygroundTab
                key={tab.id}
                tenant={tenant}
                taskId={taskId}
                tab={tab}
                newestSchema={newestSchema}
                onClose={() => onCloseTab(tab.id)}
                numberOfTabs={tabs?.length}
                versions={versions}
                majorVersions={majorVersions}
                onSelectMajorVersion={(majorVersion) => onSelectMajorVersion(tab.id, majorVersion)}
                onSelectModel={(model) => onSelectModel(tab.id, model)}
                onSelectRun={(runId) => onSelectRun(tab.id, runId)}
              />
            ))}
            <PlaygroundAddTab onAddTab={onAddAndScrollToNewTab} />
          </div>
        </PageContainer>
      </div>
      {shouldShowChat && (
        <PlaygroundChat
          tenant={tenant}
          taskId={taskId}
          playgroundState={playgroundState}
          onShowEditSchemaModal={onShowEditSchemaModal}
          improveInstructions={onToolCallImproveInstructions}
          changeModels={onToolCallChangeModels}
          generateNewInput={onToolCallGenerateNewInput}
          onCancelChatToolCallOnPlayground={onCancelChatToolCallOnPlayground}
          scrollToInput={onScrollToTop}
          scrollToOutput={onScrollToPlaygroundOutput}
        />
      )}
    </div>
  );
}
