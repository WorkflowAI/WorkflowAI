'use client';

import {
  Add16Filled,
  ArrowCircleUp16Regular,
  ArrowExpand16Regular,
  Code16Regular,
  Link16Regular,
} from '@fluentui/react-icons';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useDeployVersionModal } from '@/components/DeployIterationModal/DeployVersionModal';
import { TaskOutputViewer } from '@/components/ObjectViewer/TaskOutputViewer';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { useCopyRunURL } from '@/lib/hooks/useCopy';
import { useIsAllowed } from '@/lib/hooks/useIsAllowed';
import { taskApiRoute } from '@/lib/routeFormatter';
import { getContextWindowInformation } from '@/lib/taskRunUtils';
import { cn } from '@/lib/utils';
import { isVersionSaved } from '@/lib/versionUtils';
import { useOrFetchRunCompletions } from '@/store/fetchers';
import { useVersions } from '@/store/versions';
import { JsonSchema, TaskOutput, ToolCallPreview } from '@/types';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { ModelResponse, ReasoningStep, RunV1, VersionV1 } from '@/types/workflowAI';
import { TaskInputDict } from '@/types/workflowAI';
import { ProxyReplyView } from '../proxy-playground/proxy-messages/ProxyReplyView';
import { AIEvaluationReview } from './components/AIEvaluation/AIEvaluationReview';
import { TaskRunOutputRows } from './components/TaskRunOutputRows/TaskRunOutputRows';

type ModelOutputContentProps = {
  currentAIModel: ModelResponse | undefined;
  minimumCostAIModel: ModelResponse | undefined;
  hasInputChanged: boolean;
  minimumCostTaskRun: RunV1 | undefined;
  minimumLatencyTaskRun: RunV1 | undefined;
  onOpenTaskRun: () => void;
  onImprovePrompt: (evaluation: string) => Promise<void>;
  outputSchema: JsonSchema | undefined;
  referenceValue: Record<string, unknown> | undefined;
  onShowEditDescriptionModal: () => void;
  streamLoading: boolean;
  version: VersionV1 | undefined;
  taskOutput: TaskOutput | undefined;
  taskRun: RunV1 | undefined;
  tenant: TenantID | undefined;
  taskId: TaskID | undefined;
  taskSchemaId: TaskSchemaID | undefined;
  toolCalls: Array<ToolCallPreview> | undefined;
  reasoningSteps: ReasoningStep[] | undefined;
  isInDemoMode: boolean;
  isHideModelColumnAvaible: boolean;
  hideModelColumn: () => void;
  updateInputAndRun: (input: TaskInputDict) => Promise<void>;
  isProxy: boolean;
};

export function PlaygroundModelOutputContent(props: ModelOutputContentProps) {
  const {
    currentAIModel,
    minimumCostAIModel,
    hasInputChanged,
    minimumCostTaskRun,
    minimumLatencyTaskRun,
    onOpenTaskRun,
    onImprovePrompt,
    outputSchema: outputSchemaFromProps,
    referenceValue,
    version,
    taskOutput,
    taskRun,
    tenant,
    taskId,
    taskSchemaId,
    onShowEditDescriptionModal,
    streamLoading,
    toolCalls: toolCallsPreview,
    reasoningSteps,
    isInDemoMode,
    isHideModelColumnAvaible,
    hideModelColumn,
    updateInputAndRun,
    isProxy,
  } = props;

  const onCopyTaskRunUrl = useCopyRunURL(tenant, taskId, taskRun?.id);

  const { completions: runCompletions } = useOrFetchRunCompletions(tenant, taskId, taskRun?.id);

  const contextWindowInformation = useMemo(() => {
    return getContextWindowInformation(runCompletions);
  }, [runCompletions]);

  const router = useRouter();
  const saveVersion = useVersions((state) => state.saveVersion);

  const [isOpeningCode, setIsOpeningCode] = useState(false);
  const [isOpeningDeploy, setIsOpeningDeploy] = useState(false);
  const { checkIfSignedIn } = useIsAllowed();

  const onOpenTaskCode = useCallback(async () => {
    const versionId = version?.id;
    if (!tenant || !taskId || !taskSchemaId || !versionId) return;

    if (!checkIfSignedIn()) {
      return;
    }

    setIsOpeningCode(true);
    if (!isVersionSaved(version)) {
      await saveVersion(tenant, taskId, versionId);
    }

    router.push(
      taskApiRoute(tenant, taskId, taskSchemaId, {
        selectedVersionId: versionId,
      })
    );

    setIsOpeningCode(false);
  }, [router, tenant, taskId, taskSchemaId, version, saveVersion, checkIfSignedIn]);

  const { onDeployToClick: onDeploy } = useDeployVersionModal();
  const [isHovering, setIsHovering] = useState(false);

  const onDeployToClick = useCallback(async () => {
    const versionId = version?.id;
    if (!tenant || !taskId || !versionId) return;

    if (!checkIfSignedIn()) {
      return;
    }

    setIsOpeningDeploy(true);
    if (!isVersionSaved(version)) {
      await saveVersion(tenant, taskId, versionId);
    }

    onDeploy(versionId);
    setIsOpeningDeploy(false);
  }, [onDeploy, version, saveVersion, tenant, taskId, checkIfSignedIn]);

  const emptyMode = !taskOutput || hasInputChanged;

  const outputSchema = (version?.output_schema as JsonSchema) ?? outputSchemaFromProps;

  const [showReplyView, setShowReplyView] = useState(false);
  const showReplyButton = isProxy && !!taskRun && !showReplyView;

  const scrollToBottom = useCallback(() => {
    const proxyMessagesView = document.getElementById('playground-scroll');
    if (proxyMessagesView) {
      proxyMessagesView.scrollTo({
        top: proxyMessagesView.scrollHeight,
        behavior: 'auto',
      });
    }
  }, []);

  const onShowReplyView = useCallback(() => {
    setShowReplyView(true);
  }, []);

  useEffect(() => {
    if (showReplyView) {
      scrollToBottom();
    }
  }, [showReplyView, scrollToBottom]);

  return (
    <div
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
      className='flex flex-col w-full sm:h-full'
    >
      <div className='flex flex-col sm:flex-1 rounded-[2px] overflow-hidden my-3 border border-gray-200'>
        <TaskOutputViewer
          schema={outputSchema}
          value={taskOutput}
          referenceValue={referenceValue}
          defs={outputSchema?.$defs}
          textColor='text-gray-900'
          className={cn(
            'flex sm:flex-1 w-full border-b border-gray-200 border-dashed bg-white sm:overflow-y-scroll',
            !!taskOutput && 'min-h-[150px]'
          )}
          showTypes={emptyMode}
          showExamplesHints
          onShowEditDescriptionModal={isInDemoMode || isProxy ? undefined : onShowEditDescriptionModal}
          streamLoading={streamLoading}
          toolCalls={toolCallsPreview}
          reasoningSteps={reasoningSteps}
          showDescriptionExamples={emptyMode && !isProxy ? 'all' : undefined}
          showDescriptionPopover={!isProxy}
          defaultOpenForSteps={isProxy}
        />
        {!!taskId && !!taskRun && !hasInputChanged && !isProxy && (
          <div className='flex flex-col w-full overflow-hidden max-h-[400px]'>
            <AIEvaluationReview
              tenant={tenant}
              taskId={taskId}
              runId={taskRun.id}
              onImprovePrompt={isProxy ? undefined : onImprovePrompt}
            />
          </div>
        )}
        <TaskRunOutputRows
          currentAIModel={currentAIModel}
          minimumCostAIModel={minimumCostAIModel}
          taskRun={taskRun}
          version={version}
          minimumLatencyTaskRun={minimumLatencyTaskRun}
          minimumCostTaskRun={minimumCostTaskRun}
          showVersion={true}
          contextWindowInformation={contextWindowInformation}
          showTaskIterationDetails={true}
        />
        {showReplyView && !!taskRun && (
          <ProxyReplyView
            toolCalls={toolCallsPreview}
            input={taskRun.task_input}
            output={taskRun.task_output}
            updateInputAndRun={updateInputAndRun}
            runId={taskRun.id}
          />
        )}

        {showReplyButton && (
          <div className='flex w-full overflow-hidden py-3 px-4'>
            <Button
              variant='newDesignGray'
              size='sm'
              onClick={onShowReplyView}
              icon={<Add16Filled className='h-3.5 w-3.5' />}
            >
              Reply with {toolCallsPreview && toolCallsPreview.length > 0 ? 'Tool Call Result' : 'User Message'}
            </Button>
          </div>
        )}
      </div>

      <div className={cn('sm:flex hidden items-center justify-between', isHovering ? 'opacity-100' : 'opacity-0')}>
        <div className='flex items-center gap-2'>
          <SimpleTooltip content='Copy Link to Run'>
            <Button
              variant='newDesignGray'
              size='none'
              onClick={onCopyTaskRunUrl}
              icon={<Link16Regular className='h-4 w-4' />}
              className='h-7 w-7 border-none shadow-sm shadow-gray-400/30'
              disabled={!taskRun}
            />
          </SimpleTooltip>
          <SimpleTooltip content='View Run'>
            <Button
              variant='newDesignGray'
              size='none'
              onClick={onOpenTaskRun}
              icon={<ArrowExpand16Regular className='h-4 w-4' />}
              className='h-7 w-7 border-none shadow-sm shadow-gray-400/30'
              disabled={!taskRun}
            />
          </SimpleTooltip>
          {!isProxy && (
            <>
              <SimpleTooltip content='View Code'>
                <Button
                  variant='newDesignGray'
                  size='none'
                  onClick={onOpenTaskCode}
                  icon={<Code16Regular className='h-4 w-4' />}
                  className='h-7 w-7 border-none shadow-sm shadow-gray-400/30'
                  disabled={!taskRun}
                  loading={isOpeningCode}
                />
              </SimpleTooltip>
              <SimpleTooltip content='Deploy Version'>
                <Button
                  variant='newDesignGray'
                  size='none'
                  onClick={onDeployToClick}
                  icon={<ArrowCircleUp16Regular className='h-4 w-4' />}
                  className='h-7 w-7 border-none shadow-sm shadow-gray-400/30'
                  disabled={!taskRun || isInDemoMode}
                  loading={isOpeningDeploy}
                />
              </SimpleTooltip>
            </>
          )}
        </div>

        {isHideModelColumnAvaible && (
          <Button variant='newDesignGray' size='sm' onClick={hideModelColumn}>
            Hide Model Column
          </Button>
        )}
      </div>
    </div>
  );
}
