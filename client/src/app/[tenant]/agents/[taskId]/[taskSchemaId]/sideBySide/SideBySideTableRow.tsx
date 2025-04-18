import { Key, useMemo } from 'react';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { TaskSchemaResponseWithSchema } from '@/types/task';
import { CreateVersionRequest, TaskInputDict } from '@/types/workflowAI';
import { ModelResponse, VersionV1 } from '@/types/workflowAI';
import { SideBySideTableRowInput } from './SideBySideTableRowInput';
import { SideBySideTableRowOutput } from './SideBySideTableRowOutput';

type SideBySideTableRowProps = {
  key: Key;
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  input: TaskInputDict;
  taskSchema: TaskSchemaResponseWithSchema | undefined;
  selectedLeftVersion: VersionV1 | undefined;
  selectedRightVersion: VersionV1 | undefined;
  selectedRightModel: ModelResponse | undefined;
  onNewRunId: (runId: string | undefined, side: 'left' | 'right') => void;
};

export function SideBySideTableRow(props: SideBySideTableRowProps) {
  const {
    key,
    input,
    taskSchema,
    selectedLeftVersion,
    selectedRightVersion,
    selectedRightModel,
    tenant,
    taskId,
    taskSchemaId,
    onNewRunId,
  } = props;

  const inputSchema = taskSchema?.input_schema;
  const outputSchema = taskSchema?.output_schema;

  const leftBody: CreateVersionRequest | undefined = useMemo(() => {
    if (!selectedLeftVersion) {
      return undefined;
    }

    return {
      properties: selectedLeftVersion.properties,
      save: false,
    };
  }, [selectedLeftVersion]);

  const rightBody: CreateVersionRequest | undefined = useMemo(() => {
    if (!selectedRightVersion) {
      if (!selectedLeftVersion || !selectedRightModel) {
        return undefined;
      }

      return {
        properties: {
          ...selectedLeftVersion.properties,
          model: selectedRightModel.id,
        },
        save: false,
      };
    }

    return {
      properties: selectedRightVersion.properties,
      save: false,
    };
  }, [selectedRightVersion, selectedLeftVersion, selectedRightModel]);

  return (
    <div className='flex items-stretch w-full border-b border-gray-100 last:border-transparent' key={key}>
      <div className='flex flex-col w-[20%] border-r border-gray-100'>
        <SideBySideTableRowInput input={input} inputSchema={inputSchema} />
      </div>
      <div className='flex flex-col items-start w-[40%] border-r border-gray-100 p-4'>
        <SideBySideTableRowOutput
          outputSchema={outputSchema}
          body={leftBody}
          input={input}
          tenant={tenant}
          taskId={taskId}
          taskSchemaId={taskSchemaId}
          onNewRunId={(runId) => onNewRunId(runId, 'left')}
        />
      </div>
      <div className='flex flex-col items-start w-[40%] p-4'>
        <SideBySideTableRowOutput
          outputSchema={outputSchema}
          body={rightBody}
          input={input}
          tenant={tenant}
          taskId={taskId}
          taskSchemaId={taskSchemaId}
          onNewRunId={(runId) => onNewRunId(runId, 'right')}
        />
      </div>
    </div>
  );
}
