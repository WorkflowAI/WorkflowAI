import { useMemo } from 'react';
import { ObjectViewer } from '@/components/ObjectViewer/ObjectViewer';
import { TaskOutputViewer } from '@/components/ObjectViewer/TaskOutputViewer';
import { Loader } from '@/components/ui/Loader';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { useOrFetchCurrentTaskSchema, useOrFetchRunV1 } from '@/store/fetchers';
import { TaskID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { RunItemV1 } from '@/types/workflowAI';
import { ModelOutputErrorInformation } from '../../playground/components/ModelOutputErrorInformation';
import { checkSchemaForProxy } from '../../proxy-playground/utils';
import { PreviewBox } from './PreviewBox';
import { ProxyTaskRunHoverableInputOutputContent } from './Proxy/ProxyTaskRunHoverableInputOutputContent';

type TaskRunHoverableInputOutputContentProps = {
  runItem: RunItemV1;
};

function TaskRunHoverableInputOutputContent(props: TaskRunHoverableInputOutputContentProps) {
  const { runItem } = props;

  const { taskSchema, isInitialized: isTaskSchemaInitialized } = useOrFetchCurrentTaskSchema(
    undefined,
    runItem.task_id as TaskID,
    `${runItem.task_schema_id}` as TaskSchemaID
  );

  const { run, isInitialized: isRunInitialized } = useOrFetchRunV1(undefined, runItem.task_id as TaskID, runItem.id);

  const input = run?.task_input;
  const output = run?.task_output;

  const inputSchema = taskSchema?.input_schema;
  const outputSchema = taskSchema?.output_schema;

  const isProxy = useMemo(() => {
    if (!taskSchema) {
      return false;
    }
    return checkSchemaForProxy(taskSchema);
  }, [taskSchema]);

  const error = useMemo(() => {
    if (!runItem || !runItem.error) {
      if (!!run?.error) {
        return new Error(run.error.message);
      }
      return undefined;
    }
    return new Error(runItem.error.message);
  }, [runItem, run]);

  const isOutputEmpty = useMemo(() => {
    if (!output) {
      return true;
    }

    const otherKeys = Object.keys(output).filter((key) => key !== 'internal_agent_run_result');

    return otherKeys.length === 0;
  }, [output]);

  if (!inputSchema || !outputSchema || !isTaskSchemaInitialized || !isRunInitialized) {
    return <Loader centered className='my-10 mx-20' />;
  }
  if (isProxy && !!run && !!taskSchema) {
    return <ProxyTaskRunHoverableInputOutputContent run={run} schema={taskSchema} />;
  }

  return (
    <div className='flex flex-row w-fit max-w-[950px] text-gray-700'>
      <div className='flex-1 border-r border-gray-200 border-dashed'>
        <div className='flex flex-col'>
          <div className='text-[16px] text-gray-700 font-semibold px-4 py-3 border-b border-gray-200 border-dashed'>
            Input
          </div>
          <ObjectViewer
            value={input}
            className='max-h-[450px] min-w-80 flex-shrink-0'
            schema={inputSchema.json_schema}
            defs={inputSchema.json_schema.$defs}
          />
        </div>
      </div>
      <div className='flex-1 border-r border-gray-200 border-dashed'>
        <div className='flex flex-col min-w-80'>
          <div className='text-[16px] text-gray-700 font-semibold px-4 py-3 border-b border-gray-200 border-dashed'>
            Output
          </div>
          {!!error && (
            <div className='flex flex-col w-full flex-1 pb-4 min-w-80'>
              <ModelOutputErrorInformation errorForModel={error} />
            </div>
          )}
          {!isOutputEmpty && (
            <div className='flex flex-col w-full flex-1 px-2 overflow-hidden'>
              <TaskOutputViewer
                value={output}
                className='max-h-[450px] min-w-80 flex-shrink-0'
                schema={outputSchema.json_schema}
                defs={outputSchema.json_schema.$defs}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

type TaskRunHoverableInputOutputProps = {
  runItem: RunItemV1;
};

export function TaskRunHoverableInputOutput(props: TaskRunHoverableInputOutputProps) {
  const { runItem } = props;

  const inputPreview = runItem.task_input_preview;
  const outputPreview = runItem.task_output_preview;

  return (
    <SimpleTooltip
      tooltipClassName='bg-custom-gradient-1 p-0'
      content={<TaskRunHoverableInputOutputContent runItem={runItem} />}
      tooltipDelay={300}
    >
      <div className='flex flex-row gap-4 ml-2 mr-6 py-3.5'>
        <PreviewBox preview={inputPreview} pretty />
        {runItem.error ? (
          <PreviewBox preview={runItem.error.message} pretty={false} />
        ) : (
          <PreviewBox preview={outputPreview} pretty />
        )}
      </div>
    </SimpleTooltip>
  );
}
