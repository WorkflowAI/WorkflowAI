'use client';

import { cx } from 'class-variance-authority';
import { ObjectViewer } from '@/components';
import { TaskOutputViewer } from '@/components/ObjectViewer/TaskOutputViewer';
import { PersistantAllotment } from '@/components/PersistantAllotment';
import { TaskSchemaBadgeContainer } from '@/components/TaskSchemaBadge/TaskSchemaBadgeContainer';
import { Loader } from '@/components/ui/Loader';
import { CircleCheckbox } from '@/components/v2/Checkbox';
import { TaskSchemaID } from '@/types/aliases';
import { TaskSchemaResponseWithSchema } from '@/types/task';
import { SchemasSelector } from './schemasSelector';

type SchemaCellProps = {
  schemaId: TaskSchemaID;
  isSelected: boolean;
  onSelect: (schemaId: TaskSchemaID) => void;
  isActive: boolean;
};

export function SchemaCell(props: SchemaCellProps) {
  const { schemaId, isSelected, onSelect, isActive } = props;
  return (
    <div
      className='p-1 hover:bg-gradient-to-r hover:from-[#E0E7FF]/15 hover:to-[#C7D2FE]/15'
      onClick={() => onSelect(schemaId)}
    >
      <CircleCheckbox checked={isSelected} onClick={() => onSelect(schemaId)} className='w-4 h-4'>
        <TaskSchemaBadgeContainer schemaId={schemaId} isActive={isActive} />
      </CircleCheckbox>
    </div>
  );
}

type SchemasContentHeaderProps = {
  title: string;
};

export function SchemasContentHeader(props: SchemasContentHeaderProps) {
  const { title } = props;

  return (
    <div className='px-4 h-[48px] border-b border-gray-200 border-dashed text-gray-700 text-[16px] font-semibold flex items-center shrink-0 w-full justify-between'>
      {title}
    </div>
  );
}

type SchemasContentProps = {
  currentSchemaId: TaskSchemaID;
  taskSchema: TaskSchemaResponseWithSchema | undefined;
  isInitialized: boolean;
  visibleSchemaIds: TaskSchemaID[];
  hiddenSchemaIds: TaskSchemaID[];
  activeSchemaIds: TaskSchemaID[];
  onSelect: (schemaId: TaskSchemaID) => void;
};

export function SchemasContent(props: SchemasContentProps) {
  const { taskSchema, isInitialized, visibleSchemaIds, hiddenSchemaIds, activeSchemaIds, currentSchemaId, onSelect } =
    props;
  return (
    <div className='flex flex-row w-full h-full border-r border-gray-200'>
      <SchemasSelector
        schemaIds={visibleSchemaIds}
        archivedSchemasIds={hiddenSchemaIds}
        activeSchemasIds={activeSchemaIds}
        currentSchemaId={currentSchemaId}
        onSelect={onSelect}
      />

      {!isInitialized || !taskSchema ? (
        <Loader centered />
      ) : (
        <PersistantAllotment
          name='taskInputOutput'
          initialSize={[100, 100]}
          className={cx('flex-1 bg-gradient-to-b from-white/60 to-white/0')}
        >
          <div className='flex-1 flex flex-col overflow-hidden h-full'>
            <SchemasContentHeader title='Input' />
            <ObjectViewer
              textColor='text-gray-500'
              value={undefined}
              schema={taskSchema.input_schema.json_schema}
              defs={taskSchema.input_schema.json_schema?.$defs}
              showDescriptionExamples={undefined}
              showTypes={true}
              showDescriptionPopover={false}
            />
          </div>

          <div className='h-full flex flex-col overflow-hidden border-l border-gray-200/70'>
            <SchemasContentHeader title='Output' />
            <TaskOutputViewer
              textColor='text-gray-500'
              value={undefined}
              schema={taskSchema.output_schema.json_schema}
              defs={taskSchema.output_schema.json_schema?.$defs}
              showDescriptionExamples={undefined}
              showTypes={true}
              showDescriptionPopover={false}
            />
          </div>
        </PersistantAllotment>
      )}
    </div>
  );
}
