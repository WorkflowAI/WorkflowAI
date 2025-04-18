import { Loader2 } from 'lucide-react';
import { ObjectViewer } from '@/components/ObjectViewer/ObjectViewer';
import { SerializableTaskIOWithSchema } from '@/types/task';
import { TaskInputDict } from '@/types/workflowAI';

type SideBySideTableRowInputProps = {
  input: TaskInputDict | undefined;
  inputSchema: SerializableTaskIOWithSchema | undefined;
};

export function SideBySideTableRowInput(props: SideBySideTableRowInputProps) {
  const { input, inputSchema } = props;

  if (!inputSchema || !input) {
    return (
      <div className='flex items-center justify-center w-full h-full'>
        <Loader2 className='w-5 h-5 animate-spin text-gray-300' />
      </div>
    );
  }

  return (
    <div className='relative h-full min-h-[200px]'>
      <ObjectViewer
        value={input}
        schema={inputSchema.json_schema}
        defs={inputSchema.json_schema?.$defs}
        className='w-full absolute inset-0 overflow-y-auto'
      />
    </div>
  );
}
