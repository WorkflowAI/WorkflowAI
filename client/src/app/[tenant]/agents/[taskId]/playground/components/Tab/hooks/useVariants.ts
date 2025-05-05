import { useEffect, useMemo, useState } from 'react';
import { useOrFetchVersion } from '@/store/fetchers';
import { JsonSchema, TaskSchemaResponseWithSchema } from '@/types';
import { TaskID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';
import { VersionV1 } from '@/types/workflowAI';

type UseVariantsProps = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  versions: VersionV1[];
  taskSchema: TaskSchemaResponseWithSchema | undefined;
  variantId?: string;
};

export function useVariants(props: UseVariantsProps) {
  const { tenant, taskId, versions, taskSchema, variantId } = props;

  const versionIdForVariantId = useMemo(() => {
    return versions.find((version) => version.properties.task_variant_id === variantId)?.id;
  }, [versions, variantId]);

  const { version } = useOrFetchVersion(tenant, taskId, versionIdForVariantId);

  const inputSchema = (version?.input_schema as JsonSchema) ?? (taskSchema?.input_schema.json_schema as JsonSchema);
  const outputSchema = (version?.output_schema as JsonSchema) ?? (taskSchema?.output_schema.json_schema as JsonSchema);

  return {
    inputSchema,
    outputSchema,
  };
}

type UsePlaygroundVariantsProps = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  versions: VersionV1[];
  taskSchema: TaskSchemaResponseWithSchema | undefined;
};

export function usePlaygroundVariants(props: UsePlaygroundVariantsProps) {
  const { tenant, taskId, versions, taskSchema } = props;

  const [variantId, setVariantId] = useState<string | undefined>(undefined);

  const { inputSchema: inputSchemaForVariantId, outputSchema: outputSchemaForVariantId } = useVariants({
    tenant,
    taskId,
    versions,
    taskSchema,
    variantId,
  });

  const [inputSchema, setInputSchema] = useState<JsonSchema | undefined>(
    taskSchema?.input_schema.json_schema as JsonSchema
  );

  const [outputSchema, setOutputSchema] = useState<JsonSchema | undefined>(
    taskSchema?.output_schema.json_schema as JsonSchema
  );

  useEffect(() => {
    setInputSchema(inputSchemaForVariantId);
    setOutputSchema(outputSchemaForVariantId);
  }, [inputSchemaForVariantId, outputSchemaForVariantId]);

  useEffect(() => {
    if (!taskSchema) {
      return;
    }
    setInputSchema(taskSchema.input_schema.json_schema as JsonSchema);
    setOutputSchema(taskSchema.output_schema.json_schema as JsonSchema);
    setVariantId(taskSchema.latest_variant_id ?? undefined);
  }, [taskSchema]);

  return {
    variantId,
    setVariantId,
    inputSchema,
    outputSchema,
  };
}
