import { TaskSchemaResponseWithSchema } from '@/types/task';

export function useIsProxy(schema: TaskSchemaResponseWithSchema) {
  const inputSchema = schema.input_schema.json_schema;

  if (inputSchema.format !== 'messages') {
    return false;
  }

  return inputSchema.type === 'array' || inputSchema.type === 'object';
}
