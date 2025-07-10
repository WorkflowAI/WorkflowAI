import { SchemaNodeType } from '@/lib/schemaUtils';
import { ObjectKeyType } from '@/lib/schemaUtils';
import { JsonSchemaDefinitions, JsonValueSchema } from '@/types';
import { FileInputRequest } from '@/types/workflowAI';

export interface ValueViewerProps<T, S extends JsonValueSchema = JsonValueSchema> {
  value: T;
  referenceValue?: T;
  originalVal?: T;
  className?: string;
  editable?: boolean;
  onEdit?(keyPath: string, newVal: T, triggerSave?: boolean): void;
  onTypeChange?(keyPath: string, newType: string): void;
  schema?: S;
  defs: JsonSchemaDefinitions | undefined;
  keyPath: string;
  showTypes?: boolean;
  showTypesForFiles?: boolean;
  schemaRefName?: string;
  defaultExpanded?: boolean;
  voidValue?: Record<string, unknown> | SchemaNodeType[] | undefined;
  textColor?: string;
  supportTextWrapping?: boolean;
  flatFieldBasedConfigDict?: Record<string, ObjectKeyType>;
  errorsByKeypath?: Map<string, string>;
  flatFieldBasedConfigMode?: 'editable' | 'readonly' | 'evaluation';
  showDescriptionExamples?: 'all' | 'description' | undefined;
  allowNullToggle?: boolean;
  columnDisplay?: boolean;
  isError?: boolean;
  previewMode?: boolean;
  handleFieldKeyPositionChange?: (key: string, position: number) => void;
  transcriptions?: Record<string, string>;
  showExamplesHints?: boolean;
  showDescriptionPopover?: boolean;
  onShowEditSchemaModal?: () => void;
  onShowEditDescriptionModal?: () => void;
  fetchAudioTranscription?: (payload: FileInputRequest) => Promise<string | undefined>;
  handleUploadFile?: (
    formData: FormData,
    hash: string,
    onProgress?: (progress: number) => void
  ) => Promise<string | undefined>;
  hideCopyValue?: boolean;
  supportAnnotations?: boolean;
}

export function stringifyNil(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return 'Empty';
  }
  return typeof value !== 'string' ? `${value}` : value;
}
