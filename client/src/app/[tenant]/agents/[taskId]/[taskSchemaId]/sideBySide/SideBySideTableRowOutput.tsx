import { Loader2 } from 'lucide-react';
import { useEffect } from 'react';
import { TaskOutputViewer } from '@/components/ObjectViewer/TaskOutputViewer';
import { useOrCreateVersion, useOrRunVersion } from '@/store/fetchers';
import { TenantID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { SerializableTaskIOWithSchema } from '@/types/task';
import { TaskOutput } from '@/types/task_run';
import { CreateVersionRequest, TaskInputDict } from '@/types/workflowAI';
import { AIEvaluationReview } from '../playground/components/AIEvaluation/AIEvaluationReview';

type SideBySideTableRowOutputProps = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  outputSchema: SerializableTaskIOWithSchema | undefined;
  body: CreateVersionRequest | undefined;
  input: TaskInputDict;
  onNewRunId: (runId: string | undefined) => void;
};

export function SideBySideTableRowOutput(props: SideBySideTableRowOutputProps) {
  const { outputSchema, body, input, tenant, taskId, taskSchemaId, onNewRunId } = props;

  const { isCreatingVersion, createdVersion } = useOrCreateVersion(tenant, taskId, taskSchemaId, body);
  const { isRunningVersion, runMessage } = useOrRunVersion(tenant, taskId, taskSchemaId, createdVersion?.id, input);

  const output: TaskOutput | undefined = runMessage?.task_output;
  const isLoading = isCreatingVersion || isRunningVersion;

  useEffect(() => {
    onNewRunId(runMessage?.id);
  }, [runMessage, onNewRunId]);

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
        {isLoading && !!output && <Loader2 className='w-3 h-3 animate-spin text-gray-600' />}
        {!!runMessage && <AIEvaluationReview runId={runMessage.id} tenant={tenant} taskId={taskId} showOnlyButtons />}
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
          <Loader2 className='w-5 h-5 animate-spin text-gray-300' />
        </div>
      )}
    </div>
  );
}
