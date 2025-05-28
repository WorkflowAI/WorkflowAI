import { FileValueType } from '@/components/ObjectViewer/FileViewers/utils';
import { TaskGroupProperties_Output, ToolCallRequestWithID, ToolCallResult, VersionV1 as _VersionV1 } from './models';

export * from './models';

export interface VersionV1Properties extends TaskGroupProperties_Output {
  task_variant_id?: string | null;
}

export type VersionV1 = Omit<_VersionV1, 'properties' | 'input_schema' | 'output_schema'> & {
  properties: VersionV1Properties;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
};

export type ProxyToolCallResult = {
  id?: string;
  result?: unknown;
  tool_name?: string;
  tool_input_dict?: Record<string, unknown>;
};

export type ProxyMessageContent = {
  text?: string;
  file?: FileValueType;
  tool_call_request?: ToolCallRequestWithID;
  tool_call_result?: ProxyToolCallResult;
};

export type ProxyMessage = {
  role: 'user' | 'system' | 'assistant';
  run_id?: string;
  content: ProxyMessageContent[];
};

export type ProxyMessageWithID = ProxyMessage & {
  internal_id?: string;
};
