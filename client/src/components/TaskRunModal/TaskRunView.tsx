import { Open16Regular } from '@fluentui/react-icons';
import { useMemo } from 'react';
import { useToggle } from 'usehooks-ts';
import { ModelOutputErrorInformation } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/old-playground/components/ModelOutputErrorInformation';
import { ObjectViewer } from '@/components';
import { PersistantAllotment } from '@/components/PersistantAllotment';
import { Loader } from '@/components/ui/Loader';
import { useCopyRunURL } from '@/lib/hooks/useCopy';
import { JsonSchema, TaskRun, mapReasoningSteps } from '@/types';
import { TaskID, TenantID } from '@/types/aliases';
import { SerializableTaskIOWithSchema } from '@/types/task';
import { toolCallsFromRun } from '@/types/utils';
import { VersionV1 } from '@/types/workflowAI';
import { InternalReasoningSteps } from '../ObjectViewer/InternalReasoningSteps';
import { TaskOutputViewer } from '../ObjectViewer/TaskOutputViewer';
import { Button } from '../ui/Button';
import { SimpleTooltip } from '../ui/Tooltip';
import { PromptDialog } from './PromptDialog';
import { TaskRunDetails } from './TaskRunDetails';
import { TaskRunNavigation } from './TaskRunNavigation';
import { TaskRunRightActions } from './TaskRunRightActions';

type TaskRunViewProps = {
  tenant: TenantID | undefined;
  isInitialized: boolean;
  onClose(): void;
  onFavoriteToggle: () => void;
  onNext: (() => void) | undefined;
  onPrev: (() => void) | undefined;
  playgroundInputRoute: string | undefined;
  playgroundFullRoute: string | undefined;
  schemaInput: SerializableTaskIOWithSchema | undefined;
  schemaOutput: SerializableTaskIOWithSchema | undefined;
  version: VersionV1 | undefined;
  taskRun: TaskRun | undefined;
  taskRunIndex: number;
  totalModalRuns: number;
  transcriptions?: Record<string, string>;
};

export function TaskRunView(props: TaskRunViewProps) {
  const {
    tenant,
    isInitialized,
    onClose,
    onNext,
    onPrev,
    playgroundInputRoute,
    playgroundFullRoute,
    schemaInput: schemaInputFromProps,
    schemaOutput: schemaOutputFromProps,
    version,
    taskRun,
    taskRunIndex,
    totalModalRuns,
    transcriptions,
  } = props;
  const [promptModalVisible, togglePromptModal] = useToggle(false);

  const toolCalls = toolCallsFromRun(taskRun);

  const schemaInputSchema = (version?.input_schema as JsonSchema) ?? schemaInputFromProps?.json_schema;

  const schemaOutputSchema = (version?.output_schema as JsonSchema) ?? schemaOutputFromProps?.json_schema;

  const error = useMemo(() => {
    if (!taskRun || !taskRun.error) {
      return undefined;
    }

    return new Error(taskRun.error?.message);
  }, [taskRun]);

  const isOutputEmpty = useMemo(() => {
    if (!taskRun?.task_output) {
      return true;
    }

    const output = taskRun.task_output;
    const otherKeys = Object.keys(output).filter((key) => key !== 'internal_agent_run_result');

    return otherKeys.length === 0;
  }, [taskRun]);

  const mappedReasoningSteps = useMemo(() => mapReasoningSteps(taskRun?.reasoning_steps), [taskRun?.reasoning_steps]);

  const copyTaskRunURL = useCopyRunURL(tenant, taskRun?.task_id, taskRun?.id);

  if (!isInitialized) {
    return <Loader centered />;
  }

  if (!taskRun) {
    return <div className='flex-1 flex items-center justify-center'>AI agent run not found</div>;
  }

  return (
    <div className='flex flex-col bg-custom-gradient-1'>
      <div className='flex py-3 px-4 border-b border-dashed border-gray-200'>
        <TaskRunNavigation
          taskRunIndex={taskRunIndex}
          totalModalRuns={totalModalRuns}
          onPrev={onPrev}
          onNext={onNext}
          onClose={onClose}
        />

        <TaskRunRightActions
          togglePromptModal={togglePromptModal}
          disablePromptButton={!taskRun}
          playgroundFullRoute={playgroundFullRoute}
          copyTaskRunURL={copyTaskRunURL}
        />
      </div>

      <PersistantAllotment name='taskRunView' initialSize={[200, 100]} className='flex-1 text-sm'>
        <div className='h-full flex flex-col'>
          <div className='flex-1 flex flex-col overflow-hidden'>
            <div className='flex items-center justify-between px-4 h-[48px] border-b border-gray-200 border-dashed text-gray-700 text-[16px] font-semibold shrink-0 gap-3'>
              Input
              <div className='flex gap-1 items-center justify-center'>
                {playgroundInputRoute && (
                  <SimpleTooltip
                    content={
                      <div className='text-center'>
                        Open the playground with only the
                        <br />
                        input from this run prefilled
                      </div>
                    }
                  >
                    <Button toRoute={playgroundInputRoute} icon={<Open16Regular />} variant='newDesign' size='sm'>
                      Try Input in Playground
                    </Button>
                  </SimpleTooltip>
                )}
              </div>
            </div>
            <ObjectViewer
              value={taskRun.task_input}
              schema={schemaInputSchema}
              defs={schemaInputSchema?.$defs}
              transcriptions={transcriptions}
            />
          </div>
        </div>
        <div className='h-full flex flex-col'>
          <div className='flex flex-col flex-1 border-l border-gray-200 border-dashed ml-[0px] overflow-hidden'>
            <div className='flex items-center px-4 h-[48px] border-b border-gray-200 border-dashed text-gray-700 text-[16px] font-semibold shrink-0 gap-3'>
              Output
            </div>
            <div className='flex-1 overflow-y-auto flex flex-col'>
              {!!error && <ModelOutputErrorInformation errorForModel={error} />}
              {isOutputEmpty ? (
                <InternalReasoningSteps
                  steps={mappedReasoningSteps}
                  streamLoading={false}
                  toolCalls={toolCalls}
                  defaultOpen={true}
                />
              ) : (
                <div className='flex flex-col w-full flex-1 px-2 overflow-hidden'>
                  <TaskOutputViewer
                    value={taskRun.task_output}
                    noOverflow
                    schema={schemaOutputSchema}
                    defs={schemaOutputSchema?.$defs}
                    className='h-full w-full overflow-y-auto'
                    errorsByKeypath={undefined}
                    toolCalls={toolCalls}
                    reasoningSteps={mappedReasoningSteps}
                    defaultOpenForSteps={true}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
        <TaskRunDetails taskRun={taskRun} tenant={tenant} version={version} />
      </PersistantAllotment>

      {taskRun && !!version && (
        <PromptDialog
          open={promptModalVisible}
          onOpenChange={togglePromptModal}
          taskId={taskRun.task_id as TaskID}
          tenant={tenant}
          taskRunId={taskRun.id}
        />
      )}
    </div>
  );
}
