import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocalStorage } from 'usehooks-ts';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { TaskSchemaResponseWithSchema } from '@/types/task';
import { MajorVersion } from '@/types/workflowAI';
import { useImproveInstructions } from './useImproveInstructions';

export function usePlaygroundParameters(
  tenant: TenantID | undefined,
  taskId: TaskID,
  tabId: string,
  majorVersion: MajorVersion | undefined,
  newestSchema: TaskSchemaResponseWithSchema | undefined
) {
  const majorSchemaId = majorVersion ? (`${majorVersion?.schema_id}` as TaskSchemaID) : undefined;
  const newestSchemaId = `${newestSchema?.schema_id}` as TaskSchemaID;

  const schemaId = majorSchemaId ?? newestSchemaId;
  const variantId = majorVersion?.properties.task_variant_id ?? newestSchema?.latest_variant_id ?? undefined;

  const [showCustomParameters, setShowCustomParameters] = useLocalStorage<boolean>(
    `playground-show-custom-parameters-${tabId}-${majorVersion?.major}`,
    false
  );

  const [baseInstructions, setBaseInstructions] = useState<string | undefined>(undefined);
  const [baseTemperature, setBaseTemperature] = useState<number | undefined>(undefined);

  const [customInstructions, setCustomInstructions] = useLocalStorage<string | undefined>(
    `playground-instructions-${tabId}-${majorVersion?.major}`,
    undefined
  );
  const [customTemperature, setCustomTemperature] = useLocalStorage<number | undefined>(
    `playground-temperature-${tabId}-${majorVersion?.major}`,
    undefined
  );

  const instructions = useMemo(() => {
    return (showCustomParameters ? customInstructions ?? baseInstructions : baseInstructions) ?? '';
  }, [showCustomParameters, customInstructions, baseInstructions]);

  const temperature = useMemo(() => {
    return (showCustomParameters ? customTemperature ?? baseTemperature : baseTemperature) ?? 0;
  }, [showCustomParameters, customTemperature, baseTemperature]);

  useEffect(() => {
    if (majorVersion) {
      setBaseInstructions(majorVersion.properties.instructions);
      setBaseTemperature(majorVersion.properties.temperature);
    }
  }, [majorVersion, setBaseInstructions, setBaseTemperature]);

  const [changelog, setChangelog] = useState<string[] | undefined>(undefined);

  const onHandleSetCustomInstructions = useCallback(
    (instructions: string) => {
      setCustomInstructions(instructions);
      setCustomTemperature(temperature);

      if (instructions !== baseInstructions || temperature !== baseTemperature) {
        setShowCustomParameters(true);
      } else {
        setShowCustomParameters(false);
        setCustomInstructions(undefined);
        setCustomTemperature(undefined);
      }
    },
    [
      temperature,
      baseInstructions,
      baseTemperature,
      setCustomInstructions,
      setCustomTemperature,
      setShowCustomParameters,
    ]
  );

  const {
    onToolsChange,
    improveInstructions,
    generateInstructions,
    oldInstructions,
    resetOldInstructions,
    isLoading,
    cancelImproveInstructions,
  } = useImproveInstructions(
    tenant,
    taskId,
    schemaId,
    variantId,
    instructions,
    onHandleSetCustomInstructions,
    setChangelog
  );

  const resetImprovedInstructions = useCallback(() => {
    setChangelog(undefined);
    setCustomInstructions(oldInstructions ?? '');
    resetOldInstructions();
  }, [setChangelog, resetOldInstructions, oldInstructions, setCustomInstructions]);

  const approveImprovedInstructions = useCallback(() => {
    setChangelog(undefined);
    resetOldInstructions();
  }, [setChangelog, resetOldInstructions]);

  const onMoveToPrevious = useCallback(() => {
    setShowCustomParameters(false);
  }, [setShowCustomParameters]);

  const onMoveToNext = useCallback(() => {
    setShowCustomParameters(true);
  }, [setShowCustomParameters]);

  const onHandleSetCustomTemperature = useCallback(
    (temperature: number) => {
      setCustomTemperature(temperature);
      setCustomInstructions(instructions);

      if (instructions !== baseInstructions || temperature !== baseTemperature) {
        setShowCustomParameters(true);
      } else {
        setShowCustomParameters(false);
        setCustomInstructions(undefined);
        setCustomTemperature(undefined);
      }
    },
    [
      instructions,
      baseInstructions,
      baseTemperature,
      setCustomInstructions,
      setCustomTemperature,
      setShowCustomParameters,
    ]
  );

  const areThereCustomParameters = useMemo(() => {
    return customInstructions !== undefined || customTemperature !== undefined;
  }, [customInstructions, customTemperature]);

  const resetHistoryIndex = useCallback(() => {
    setShowCustomParameters(false);
  }, [setShowCustomParameters]);

  const showPreviouse = useMemo(() => {
    if (baseInstructions === undefined && baseTemperature === undefined) {
      return false;
    }
    return showCustomParameters;
  }, [showCustomParameters, baseInstructions, baseTemperature]);

  const showNext = useMemo(() => {
    if (baseInstructions === undefined && baseTemperature === undefined) {
      return false;
    }
    return !showCustomParameters && areThereCustomParameters;
  }, [showCustomParameters, areThereCustomParameters, baseInstructions, baseTemperature]);

  return {
    instructions,
    temperature,
    setInstructions: onHandleSetCustomInstructions,
    setTemperature: onHandleSetCustomTemperature,

    onMoveToPreviousParameters: showPreviouse ? onMoveToPrevious : undefined,
    onMoveToNextParameters: showNext ? onMoveToNext : undefined,

    oldInstructions,
    changelog,
    isLoading,
    resetImprovedInstructions,
    approveImprovedInstructions,
    onToolsChange,

    improveInstructions,
    generateInstructions,
    cancelImproveInstructions,

    resetHistoryIndex,
  };
}
