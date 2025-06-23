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
import { SideBySideVersionPopoverItem } from '../../side-by-side/SideBySideVersionPopoverItem';
import { SideBySideVersionPopoverModelItem } from '../../side-by-side/SideBySideVersionPopoverModelItem';
import { AdvancedSettings } from '../hooks/useProxyPlaygroundSearchParams';
import { ProxyPlaygroundModels, addAdvencedSettingsToProperties, getModelAndReasoning } from '../utils';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  schemaId: TaskSchemaID;

  runs: (RunV1 | undefined)[];
  versionsForRuns: Record<string, VersionV1>;
  outputModels: ProxyPlaygroundModels;
  models: ModelResponse[];

  proxyMessages: ProxyMessage[] | undefined;
  proxyToolCalls: (ToolKind | Tool_Output)[] | undefined;
  advancedSettings: AdvancedSettings;

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
    advancedSettings,
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

      const { model: modelId } = getModelAndReasoning(index, outputModels);
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
        enabled_tools: proxyToolCalls,
        messages: proxyMessages,
      };

      const propertiesWithAdvancedSettings = addAdvencedSettingsToProperties(properties, advancedSettings);

      try {
        const { id: versionId } = await createVersion(tenant, taskId, schemaId, {
          properties: propertiesWithAdvancedSettings,
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
      proxyToolCalls,
      proxyMessages,
      createVersion,
      tenant,
      taskId,
      schemaId,
      saveVersion,
      setVersionIdForCode,
      advancedSettings,
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
