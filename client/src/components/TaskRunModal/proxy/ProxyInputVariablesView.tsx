import { useMemo } from 'react';
import { ObjectViewer } from '@/components';
import { InitInputFromSchemaMode } from '@/lib/schemaUtils';
import { initInputFromSchema } from '@/lib/schemaUtils';
import { mergeTaskInputAndVoid } from '@/lib/schemaVoidUtils';
import { TaskSchemaResponseWithSchema } from '@/types';

type Props = {
  input: Record<string, unknown> | undefined;
  schema: TaskSchemaResponseWithSchema;
  title: string;
};

export function ProxyInputVariablesView(props: Props) {
  const { input, schema, title } = props;

  const inputSchema = schema.input_schema.json_schema;

  const voidInput = useMemo(() => {
    if (!inputSchema) return undefined;
    return initInputFromSchema(inputSchema, inputSchema.$defs, InitInputFromSchemaMode.VOID);
  }, [inputSchema]);

  const generatedInputWithVoid = useMemo(() => {
    if (!input) return voidInput;
    return mergeTaskInputAndVoid(input, voidInput);
  }, [input, voidInput]);

  return (
    <div className='flex flex-col h-full w-full overflow-hidden'>
      <div className='flex w-full h-12 border-b border-dashed border-gray-200 items-center px-4'>
        <div className='text-[16px] font-semibold text-gray-700'>{title}</div>
      </div>
      <div className='flex w-full max-h-[calc(100%-48px)] overflow-y-auto'>
        <ObjectViewer
          schema={inputSchema}
          defs={inputSchema?.$defs}
          value={generatedInputWithVoid}
          voidValue={voidInput}
          editable={true}
          textColor='text-gray-500'
          className='flex w-full h-max'
          showDescriptionPopover={false}
        />
      </div>
    </div>
  );
}
