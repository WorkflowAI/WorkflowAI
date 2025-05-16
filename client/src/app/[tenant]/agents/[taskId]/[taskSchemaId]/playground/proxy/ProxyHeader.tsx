import { useMemo } from 'react';
import { useOrExtractTemplete } from '@/store/extract_templete';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { JsonSchema } from '@/types/json_schema';
import { GeneralizedTaskInput } from '@/types/task_run';
import { ProxyMessage, ToolKind, Tool_Output } from '@/types/workflowAI';
import { ProxyHeaderWithInput } from './ProxyHeaderWithInput';
import { ProxyHeaderWithoutInput } from './ProxyHeaderWithoutInput';

function mergeJsonSchemas(inputSchema: JsonSchema, templeteInputSchema: JsonSchema): JsonSchema {
  return {
    ...inputSchema,
    properties: { ...inputSchema.properties, ...templeteInputSchema.properties },
  };
}

interface Props {
  inputSchema: JsonSchema | undefined;
  input: GeneralizedTaskInput | undefined;
  setInput: (input: GeneralizedTaskInput) => void;
  temperature: number;
  setTemperature: (temperature: number) => void;
  handleRunTasks: () => void;
  toolCalls: (ToolKind | Tool_Output)[] | undefined;
  setToolCalls: (toolCalls: (ToolKind | Tool_Output)[] | undefined) => void;
  maxHeight: number | undefined;
  proxyMessages: ProxyMessage[] | undefined;
  setProxyMessages: (proxyMessages: ProxyMessage[] | undefined) => void;
  hasProxyInput: boolean;
  tenant: TenantID | undefined;
  taskId: TaskID;
}

export function ProxyHeader(props: Props) {
  const {
    inputSchema,
    input,
    setInput,
    temperature,
    setTemperature,
    handleRunTasks,
    toolCalls,
    setToolCalls,
    maxHeight,
    proxyMessages,
    setProxyMessages,
    hasProxyInput,
    tenant,
    taskId,
  } = props;

  const allProxyMessages = useMemo(() => {
    let result: ProxyMessage[] = [];
    if (proxyMessages) {
      result = [...proxyMessages];
    }

    if (input && 'workflowai.replies' in input) {
      const inputMessages = input['workflowai.replies'] as ProxyMessage[];
      result = [...result, ...inputMessages];
    }

    if (input && 'messages' in input) {
      const inputMessages = input['messages'] as ProxyMessage[];
      result = [...result, ...inputMessages];
    }

    return result;
  }, [proxyMessages, input]);

  const { schema: templeteInputSchema } = useOrExtractTemplete(tenant, taskId, allProxyMessages);
  const mergedSchema = useMemo(() => {
    if (!inputSchema || !templeteInputSchema) {
      return inputSchema;
    }
    return mergeJsonSchemas(inputSchema, templeteInputSchema);
  }, [inputSchema, templeteInputSchema]);

  if (hasProxyInput) {
    return (
      <ProxyHeaderWithInput
        tenant={tenant}
        taskId={taskId}
        inputSchema={inputSchema}
        input={input}
        setInput={setInput}
        temperature={temperature}
        setTemperature={setTemperature}
        handleRunTasks={handleRunTasks}
        toolCalls={toolCalls}
        setToolCalls={setToolCalls}
        maxHeight={maxHeight}
        proxyMessages={proxyMessages}
        setProxyMessages={setProxyMessages}
      />
    );
  }

  return (
    <ProxyHeaderWithoutInput
      tenant={tenant}
      taskId={taskId}
      input={input}
      setInput={setInput}
      temperature={temperature}
      setTemperature={setTemperature}
      handleRunTasks={handleRunTasks}
      toolCalls={toolCalls}
      setToolCalls={setToolCalls}
      maxHeight={maxHeight}
    />
  );
}
