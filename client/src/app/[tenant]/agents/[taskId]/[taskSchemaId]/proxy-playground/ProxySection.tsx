import { useCallback, useMemo } from 'react';
import { ExtractTempleteError } from '@/store/extract_templete';
import { TaskID, TenantID } from '@/types/aliases';
import { JsonSchema } from '@/types/json_schema';
import { GeneralizedTaskInput } from '@/types/task_run';
import { MajorVersion, ProxyMessage, ToolKind, Tool_Output, VersionV1 } from '@/types/workflowAI';
import { ProxyImproveMessagesControls } from './hooks/useProxyImproveMessages';
import { useProxyInputStructure } from './hooks/useProxyInputStructure';
import { ProxyInput } from './input-section/ProxyInput';
import { ProxyParameters } from './parameters-section/ProxyParameters';
import { createEmptyMessage } from './proxy-messages/utils';
import { removeInputEntriesNotMatchingSchema } from './utils';

interface Props {
  extractedInputSchema: JsonSchema | undefined;
  setExtractedInputSchema: (inputSchema: JsonSchema | undefined) => void;
  inputVariblesKeys: string[] | undefined;
  error: ExtractTempleteError | undefined;

  input: GeneralizedTaskInput | undefined;
  setInput: (input: GeneralizedTaskInput) => void;

  proxyMessages: ProxyMessage[] | undefined;
  setProxyMessages: (proxyMessages: ProxyMessage[] | undefined) => void;

  temperature: number;
  setTemperature: (temperature: number) => void;

  toolCalls: (ToolKind | Tool_Output)[] | undefined;
  setToolCalls: (toolCalls: (ToolKind | Tool_Output)[] | undefined) => void;

  maxHeight: number | undefined;

  tenant: TenantID | undefined;
  taskId: TaskID;

  matchedMajorVersion: MajorVersion | undefined;
  majorVersions: MajorVersion[];
  useParametersFromMajorVersion: (version: MajorVersion) => void;

  showSaveAllVersions: boolean;
  onSaveAllVersions: () => void;

  versionsForRuns: Record<string, VersionV1>;
  improveMessagesControls: ProxyImproveMessagesControls;
}

export function ProxySection(props: Props) {
  const {
    extractedInputSchema,
    setExtractedInputSchema,
    inputVariblesKeys,
    error,
    input,
    setInput,
    temperature,
    setTemperature,
    toolCalls,
    setToolCalls,
    maxHeight,
    proxyMessages,
    setProxyMessages,
    tenant,
    taskId,
    matchedMajorVersion,
    majorVersions,
    useParametersFromMajorVersion,
    showSaveAllVersions,
    onSaveAllVersions,
    versionsForRuns,
    improveMessagesControls,
  } = props;

  const messagesWithDefaultSystemMessage = useMemo(() => {
    if (!proxyMessages || proxyMessages?.length === 0) {
      return [createEmptyMessage('system')];
    }
    return proxyMessages;
  }, [proxyMessages]);

  const onMoveToVersion = useCallback(
    (message: ProxyMessage) => {
      if (
        !!proxyMessages &&
        proxyMessages?.length === 1 &&
        proxyMessages[0].role === 'system' &&
        proxyMessages[0].content === undefined
      ) {
        setProxyMessages([message]);
      } else {
        setProxyMessages([...(proxyMessages ?? []), message]);
      }
    },
    [proxyMessages, setProxyMessages]
  );

  const {
    messages: inputMessages,
    setMessages: setInputMessages,
    cleanInput,
    setCleanInput,
  } = useProxyInputStructure({
    input,
    setInput,
  });

  const cleanMatchingInput: Record<string, unknown> | undefined = useMemo(() => {
    if (!cleanInput) {
      return undefined;
    }
    const result = removeInputEntriesNotMatchingSchema(cleanInput, extractedInputSchema);
    if (Array.isArray(result)) {
      return cleanInput;
    }
    return result;
  }, [cleanInput, extractedInputSchema]);

  return (
    <div
      className='flex w-full items-stretch border-b border-gray-200 border-dashed overflow-hidden'
      style={maxHeight ? { maxHeight } : undefined}
    >
      <div className='w-1/2 border-r border-gray-200 border-dashed overflow-y-auto flex' id='proxy-messages-view'>
        <ProxyInput
          inputMessages={inputMessages}
          setInputMessages={setInputMessages}
          tenant={tenant}
          taskId={taskId}
          inputSchema={extractedInputSchema}
          setInputSchema={setExtractedInputSchema}
          input={cleanMatchingInput}
          setInput={setCleanInput}
          onMoveToVersion={onMoveToVersion}
          inputVariblesKeys={inputVariblesKeys}
        />
      </div>
      <div className='w-1/2'>
        <ProxyParameters
          messages={messagesWithDefaultSystemMessage}
          setMessages={setProxyMessages}
          temperature={temperature}
          setTemperature={setTemperature}
          toolCalls={toolCalls}
          setToolCalls={setToolCalls}
          matchedMajorVersion={matchedMajorVersion}
          majorVersions={majorVersions}
          useParametersFromMajorVersion={useParametersFromMajorVersion}
          showSaveAllVersions={showSaveAllVersions}
          onSaveAllVersions={onSaveAllVersions}
          versionsForRuns={versionsForRuns}
          inputVariblesKeys={inputVariblesKeys}
          error={error}
          improveMessagesControls={improveMessagesControls}
        />
      </div>
    </div>
  );
}
