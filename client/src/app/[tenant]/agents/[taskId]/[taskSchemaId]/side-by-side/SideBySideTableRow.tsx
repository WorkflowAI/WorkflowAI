import { useMemo, useState } from 'react';
import { hashInput } from '@/store/utils';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { TaskSchemaResponseWithSchema } from '@/types/task';
import { CreateVersionRequest, TaskInputDict } from '@/types/workflowAI';
import { ModelResponse, VersionV1 } from '@/types/workflowAI';
import { SideBySideTableRowInput } from './SideBySideTableRowInput';
import { SideBySideTableRowOutput } from './SideBySideTableRowOutput';
import { useSideBySideRowStatsEffect } from './useSideBySideRowStatsEffect';

type SideBySideTableRowProps = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  input: TaskInputDict;
  taskSchema: TaskSchemaResponseWithSchema;
  selectedLeftVersion: VersionV1 | undefined;
  selectedRightVersion: VersionV1 | undefined;
  selectedRightModel: ModelResponse | undefined;
};

export function SideBySideTableRow(props: SideBySideTableRowProps) {
  const {
    input,
    taskSchema,
    selectedLeftVersion,
    selectedRightVersion,
    selectedRightModel,
    tenant,
    taskId,
    taskSchemaId,
  } = props;

  const [isHovering, setIsHovering] = useState(false);

  const inputSchema = taskSchema.input_schema;
  const outputSchema = taskSchema.output_schema;

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

  const inputHash = useMemo(() => hashInput(input), [input]);

  const { left: leftStats, right: rightStats } = useSideBySideRowStatsEffect(
    tenant,
    taskId,
    taskSchemaId,
    inputHash,
    selectedLeftVersion?.id,
    selectedRightVersion?.id,
    selectedRightModel?.id
  );

  return (
    <div
      className='flex items-stretch w-full border-b border-gray-100 last:border-transparent'
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
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
          isHovering={isHovering}
          inputHash={inputHash}
          versionId={selectedLeftVersion?.id}
          modelId={undefined}
          stats={leftStats}
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
          isHovering={isHovering}
          inputHash={inputHash}
          versionId={selectedRightVersion?.id}
          modelId={selectedRightModel?.id}
          stats={rightStats}
        />
      </div>
    </div>
  );
}
