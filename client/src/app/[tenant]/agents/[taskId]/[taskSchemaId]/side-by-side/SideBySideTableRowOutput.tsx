import { AlertTriangle, Loader2 } from 'lucide-react';
import { useEffect } from 'react';
import { TaskOutputViewer } from '@/components/ObjectViewer/TaskOutputViewer';
import { useOrRunVersion } from '@/store/run_version';
import { useSideBySideStore } from '@/store/side_by_side';
import { useOrCreateVersion } from '@/store/versions';
import { TenantID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { SerializableTaskIOWithSchema } from '@/types/task';
import { TaskOutput } from '@/types/task_run';
import { CreateVersionRequest, TaskInputDict } from '@/types/workflowAI';
import { AIEvaluationReview } from '../old-playground/components/AIEvaluation/AIEvaluationReview';
import { useFetchTaskRunUntilCreated } from '../old-playground/hooks/useFetchTaskRunUntilCreated';
import { SideBySideTableRowOutputStats } from './SideBySideTableRowOutputStats';
import { SideBySideRowStats } from './useSideBySideRowStatsEffect';

type SideBySideTableRowOutputProps = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  outputSchema: SerializableTaskIOWithSchema | undefined;
  body: CreateVersionRequest | undefined;
  input: TaskInputDict;
  isHovering: boolean;
  inputHash: string;
  versionId: string | undefined;
  modelId: string | undefined;
  stats: SideBySideRowStats;
};

export function SideBySideTableRowOutput(props: SideBySideTableRowOutputProps) {
  const { outputSchema, body, input, tenant, taskId, taskSchemaId, isHovering, inputHash, versionId, modelId, stats } =
    props;

  const {
    isCreatingVersion,
    createdVersion,
    error: createVersionError,
  } = useOrCreateVersion(tenant, taskId, taskSchemaId, body);

  const {
    isRunningVersion,
    runMessage,
    error: runVersionError,
  } = useOrRunVersion(tenant, taskId, taskSchemaId, createdVersion?.id, input);

  const error = createVersionError ?? runVersionError;

  const output: TaskOutput | undefined = runMessage?.task_output;
  const isLoading = isCreatingVersion || isRunningVersion;

  const runId = runMessage?.id;

  const fetchTaskRunUntilCreated = useFetchTaskRunUntilCreated();
  const addRunId = useSideBySideStore((state) => state.addRunId);

  useEffect(() => {
    if (!isLoading && !!runId) {
      fetchTaskRunUntilCreated(tenant, taskId, runId);
      addRunId(tenant, taskId, taskSchemaId, inputHash, versionId, modelId, runId);
    }
  }, [
    isLoading,
    fetchTaskRunUntilCreated,
    runId,
    tenant,
    taskId,
    taskSchemaId,
    inputHash,
    versionId,
    modelId,
    addRunId,
  ]);

  if (!body) {
    return <div className='flex items-center justify-center w-full h-full'></div>;
  }

  if (!outputSchema) {
    return (
      <div className='flex items-center justify-center w-full h-full'>
        <Loader2 className='w-5 h-5 animate-spin text-gray-300' />
      </div>
    );
  }

  return (
    <div className='flex flex-col h-max w-full border border-gray-200 rounded-[2px]'>
      <div className='flex flex-row justify-between items-center w-full pl-3 pr-2 h-[38px] border-b border-gray-200 bg-gray-100'>
        <div className='text-[13px] font-medium text-gray-500'>Output</div>
        <div className='flex flex-row gap-1 items-center'>
          {isHovering && !isLoading && !!runId && <SideBySideTableRowOutputStats stats={stats} />}
          {isLoading && <Loader2 className='w-3 h-3 animate-spin text-gray-600' />}
          {!!runId && !isLoading && (
            <AIEvaluationReview
              runId={runMessage.id}
              tenant={tenant}
              taskId={taskId}
              showOnlyButtons
              pollingInterval={5000}
            />
          )}
        </div>
      </div>
      {output ? (
        <TaskOutputViewer
          value={output}
          noOverflow
          schema={outputSchema.json_schema}
          defs={outputSchema.json_schema?.$defs}
          className='max-h-[400px] w-full overflow-y-auto'
          errorsByKeypath={undefined}
        />
      ) : (
        <div className='flex items-center justify-center w-full h-full min-h-[150px]'>
          {error ? (
            <div className='flex flex-col items-center justify-center w-full h-full'>
              <AlertTriangle size={20} className='text-gray-400' />
              <div className='pt-4 mx-2 text-gray-700 text-[14px] font-medium'>{error.name}</div>
              <div className='pt-0.5 mx-2 text-gray-500 text-[12px] text-center whitespace-pre-line'>
                {error.message}
              </div>
            </div>
          ) : (
            <Loader2 className='w-5 h-5 animate-spin text-gray-300' />
          )}
        </div>
      )}
    </div>
  );
}
