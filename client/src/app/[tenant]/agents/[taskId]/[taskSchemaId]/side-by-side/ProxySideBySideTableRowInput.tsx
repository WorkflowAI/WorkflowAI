import { Loader2 } from 'lucide-react';
import { useMemo } from 'react';
import { ObjectViewer } from '@/components/ObjectViewer/ObjectViewer';
import { InitInputFromSchemaMode, initInputFromSchema } from '@/lib/schemaUtils';
import { mergeTaskInputAndVoid } from '@/lib/schemaVoidUtils';
import { SerializableTaskIOWithSchema } from '@/types/task';
import { TaskInputDict } from '@/types/workflowAI';
import { useProxyInputStructure } from '../proxy-playground/hooks/useProxyInputStructure';
import { ProxyMessagesView } from '../proxy-playground/proxy-messages/ProxyMessagesView';
import { numberOfInputVariblesInInputSchema, repairMessageKeyInInput } from '../proxy-playground/utils';

type Props = {
  input: TaskInputDict;
  inputSchema: SerializableTaskIOWithSchema;
};

export function ProxySideBySideTableRowInput(props: Props) {
  const { input, inputSchema } = props;

  const repairedInput = useMemo(() => {
    return repairMessageKeyInInput(input);
  }, [input]);

  const { cleanInput, messages: inputMessages } = useProxyInputStructure({
    input: repairedInput,
  });

  const voidInput = useMemo(() => {
    if (!inputSchema) return undefined;
    return initInputFromSchema(cleanInput, inputSchema.json_schema?.$defs, InitInputFromSchemaMode.VOID);
  }, [inputSchema, cleanInput]);

  const generatedInputWithVoid = useMemo(() => {
    if (!cleanInput) return voidInput;
    return mergeTaskInputAndVoid(cleanInput, voidInput);
  }, [cleanInput, voidInput]);

  const showInputVariables = useMemo(() => {
    return numberOfInputVariblesInInputSchema(inputSchema.json_schema) > 0;
  }, [inputSchema.json_schema]);

  if (!inputSchema || !input) {
    return (
      <div className='flex items-center justify-center w-full h-full'>
        <Loader2 className='w-5 h-5 animate-spin text-gray-300' />
      </div>
    );
  }

  return (
    <div className='flex flex-col w-full overflow-y-auto items-start max-h-[475px]'>
      {!!showInputVariables && (
        <>
          <div className='flex w-full h-10 border-b border-dashed border-gray-200 items-center px-4 flex-shrink-0'>
            <div className='text-[14px] font-semibold text-gray-700'>Version Variables</div>
          </div>
          <ObjectViewer
            schema={inputSchema.json_schema}
            defs={inputSchema.json_schema?.$defs}
            value={generatedInputWithVoid}
            voidValue={voidInput}
            editable={true}
            textColor='text-gray-500'
            className='flex w-full h-max border-b border-gray-200 border-dashed flex-shrink-0 min-h-max'
            showDescriptionPopover={false}
          />
        </>
      )}
      {!!inputMessages?.length && (
        <>
          <div className='flex w-full h-10 border-b border-dashed border-gray-200 items-center px-4 flex-shrink-0'>
            <div className='text-[14px] font-semibold text-gray-700'>Messages</div>
          </div>
          <ProxyMessagesView
            messages={inputMessages}
            className='flex w-full h-max px-4 py-2'
            supportRunDetails={false}
            supportOpeningInPlayground={false}
            scrollToLastMessage={true}
          />
        </>
      )}
    </div>
  );
}
