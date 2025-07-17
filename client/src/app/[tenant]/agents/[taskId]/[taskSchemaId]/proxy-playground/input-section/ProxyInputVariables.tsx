import { cloneDeep } from 'lodash';
import { set } from 'lodash';
import { useCallback, useMemo } from 'react';
import { ObjectViewer } from '@/components/ObjectViewer/ObjectViewer';
import { FieldType, InitInputFromSchemaMode, changeFileTypeInSchema } from '@/lib/schemaUtils';
import { initInputFromSchema } from '@/lib/schemaUtils';
import { mergeTaskInputAndVoid } from '@/lib/schemaVoidUtils';
import { useAudioTranscriptions } from '@/store/audio_transcriptions';
import { useUpload } from '@/store/upload';
import { TaskID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';
import { JsonSchema } from '@/types/json_schema';
import { fixProxyInputIfNeeded } from '../proxy-messages/utils';

type Props = {
  inputSchema: JsonSchema | undefined;
  setInputSchema?: (inputSchema: JsonSchema | undefined) => void;
  input: Record<string, unknown> | undefined;
  setInput: (input: Record<string, unknown>) => void;
  tenant: TenantID | undefined;
  taskId: TaskID;
};

export function ProxyInputVariables(props: Props) {
  const { inputSchema, setInputSchema, input, setInput, tenant, taskId } = props;

  const fixedInput = useMemo(() => {
    if (!input) return input;
    return fixProxyInputIfNeeded(input);
  }, [input]);

  const voidInput = useMemo(() => {
    if (!inputSchema) return undefined;
    return initInputFromSchema(inputSchema, inputSchema.$defs, InitInputFromSchemaMode.VOID);
  }, [inputSchema]);

  const generatedInputWithVoid = useMemo(() => {
    if (!fixedInput) return voidInput;
    return mergeTaskInputAndVoid(fixedInput, voidInput);
  }, [fixedInput, voidInput]);

  const handleEdit = useCallback(
    (keyPath: string, newVal: unknown) => {
      const newInput = cloneDeep(fixedInput) || {};
      set(newInput, keyPath, newVal);
      setInput(newInput);
    },
    [fixedInput, setInput]
  );

  const handleTypeChange = useCallback(
    (keyPath: string, newType: FieldType) => {
      const newInput = cloneDeep(fixedInput) || {};
      set(newInput, keyPath, undefined);
      setInput(newInput);

      if (inputSchema && setInputSchema) {
        const newSchema = changeFileTypeInSchema(inputSchema, keyPath, newType);
        setInputSchema(newSchema);
      }
    },
    [fixedInput, setInput, inputSchema, setInputSchema]
  );

  const fetchAudioTranscription = useAudioTranscriptions((state) => state.fetchAudioTranscription);

  const { getUploadURL } = useUpload();
  const handleUploadFile = useCallback(
    async (formData: FormData, hash: string, onProgress?: (progress: number) => void) => {
      if (!tenant || !taskId) return undefined;
      return getUploadURL({
        tenant,
        taskId,
        form: formData,
        hash,
        onProgress,
      });
    },
    [getUploadURL, tenant, taskId]
  );

  return (
    <div className='flex flex-col min-h-[90px] pb-2 w-full border-b border-gray-200 border-dashed'>
      <ObjectViewer
        schema={inputSchema}
        defs={inputSchema?.$defs}
        value={generatedInputWithVoid}
        voidValue={voidInput}
        editable={true}
        onEdit={handleEdit}
        onTypeChange={setInputSchema ? handleTypeChange : undefined}
        textColor='text-gray-500'
        fetchAudioTranscription={fetchAudioTranscription}
        handleUploadFile={handleUploadFile}
        className='h-max'
        showDescriptionPopover={false}
      />
    </div>
  );
}
