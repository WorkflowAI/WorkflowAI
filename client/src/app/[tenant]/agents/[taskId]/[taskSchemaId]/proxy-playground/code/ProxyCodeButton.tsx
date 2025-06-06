import { Code16Regular } from '@fluentui/react-icons';
import { useCallback, useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/Popover';
import { isVersionSaved } from '@/lib/versionUtils';
import { useVersions } from '@/store/versions';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import {
  ModelResponse,
  ProxyMessage,
  RunV1,
  TaskGroupProperties_Input,
  ToolKind,
  Tool_Output,
  VersionV1,
} from '@/types/workflowAI';
import { PlaygroundModels } from '../../playground/hooks/utils';
import { SideBySideVersionPopoverItem } from '../../side-by-side/SideBySideVersionPopoverItem';
import { SideBySideVersionPopoverModelItem } from '../../side-by-side/SideBySideVersionPopoverModelItem';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  schemaId: TaskSchemaID;

  runs: (RunV1 | undefined)[];
  versionsForRuns: Record<string, VersionV1>;
  outputModels: PlaygroundModels;
  models: ModelResponse[];

  proxyMessages: ProxyMessage[] | undefined;
  proxyToolCalls: (ToolKind | Tool_Output)[] | undefined;
  temperature: number | undefined;

  setVersionIdForCode: (versionId: string | undefined) => void;
};

export function ProxyCodeButton(props: Props) {
  const {
    runs,
    versionsForRuns,
    outputModels,
    models,
    tenant,
    taskId,
    proxyMessages,
    proxyToolCalls,
    temperature,
    schemaId,
    setVersionIdForCode,
  } = props;

  const [open, setOpen] = useState(false);

  const entries: { version: VersionV1 | undefined; model: ModelResponse | undefined }[] = useMemo(() => {
    const result: { version: VersionV1 | undefined; model: ModelResponse | undefined }[] = [];
    runs.forEach((run, index) => {
      const version = !!run?.id ? versionsForRuns?.[run.version.id] : undefined;
      if (version) {
        result.push({ version, model: undefined });
        return;
      }

      const modelId = outputModels?.[index] ?? undefined;
      if (modelId) {
        const model = models.find((model) => model.id === modelId);
        if (model) {
          result.push({ version: undefined, model });
        }
      }
    });
    return result;
  }, [runs, versionsForRuns, outputModels, models]);

  const [isLoading, setIsLoading] = useState(false);
  const saveVersion = useVersions((state) => state.saveVersion);
  const createVersion = useVersions((state) => state.createVersion);

  const onSelectedVersion = useCallback(
    async (version: VersionV1) => {
      setOpen(false);
      setIsLoading(true);

      if (!isVersionSaved(version)) {
        try {
          await saveVersion(tenant, taskId, version.id);
        } catch (error) {
          console.error('Error saving version', error);
          setIsLoading(false);
          return;
        }
      }

      setVersionIdForCode(version.id);
      setIsLoading(false);
    },
    [setOpen, setIsLoading, saveVersion, tenant, taskId, setVersionIdForCode]
  );

  const onSelectedModelId = useCallback(
    async (modelId: string) => {
      setOpen(false);
      setIsLoading(true);

      const properties: TaskGroupProperties_Input = {
        model: modelId,
        temperature: temperature,
        enabled_tools: proxyToolCalls,
        messages: proxyMessages,
      };

      try {
        const { id: versionId } = await createVersion(tenant, taskId, schemaId, {
          properties,
        });

        await saveVersion(tenant, taskId, versionId);

        setVersionIdForCode(versionId);
        setIsLoading(false);
      } catch (error) {
        console.error('Error creating version', error);
        setIsLoading(false);
      }
    },
    [
      setOpen,
      temperature,
      proxyToolCalls,
      proxyMessages,
      createVersion,
      tenant,
      taskId,
      schemaId,
      saveVersion,
      setVersionIdForCode,
    ]
  );

  const handleSetVersionIdForCode = useCallback(
    (versionId: string | undefined) => {
      setOpen(false);
      setVersionIdForCode(versionId);
    },
    [setVersionIdForCode]
  );

  return (
    <div>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant='newDesign' icon={<Code16Regular />} className='w-9 h-9 px-0 py-0' loading={isLoading} />
        </PopoverTrigger>
        <PopoverContent
          className='max-w-[90vw] w-fit overflow-auto max-h-[362px] py-2 px-1 rounded-[2px] mx-2'
          align='center'
        >
          {entries.map((entry) => {
            const { version, model } = entry;

            if (version) {
              return (
                <SideBySideVersionPopoverItem
                  key={version.id}
                  version={version}
                  onClick={() => onSelectedVersion(version)}
                  setVersionIdForCode={handleSetVersionIdForCode}
                />
              );
            }

            if (model) {
              return (
                <SideBySideVersionPopoverModelItem
                  key={model.id}
                  model={model}
                  baseVersion={undefined}
                  onClick={() => onSelectedModelId(model.id)}
                  hidePrice={true}
                  className='pl-2'
                />
              );
            }

            return null;
          })}
        </PopoverContent>
      </Popover>
    </div>
  );
}
