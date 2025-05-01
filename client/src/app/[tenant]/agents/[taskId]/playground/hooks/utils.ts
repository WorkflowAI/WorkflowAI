import { nanoid } from 'nanoid';
import { MajorVersion } from '@/types/workflowAI';

export type Tab = {
  id: string;
  majorVersion: MajorVersion | undefined;
  modelId: string | undefined;
  runId: string | undefined;
};

export function fixInvalidTabs(tabs: Tab[] | undefined): Tab[] | undefined {
  if (!tabs) {
    return undefined;
  }

  const result = tabs.map((tab) => {
    const tabId = tab.id === 'undefined' || tab.id === '' || !tab.id ? nanoid(10) : tab.id;

    return {
      ...tab,
      id: tabId,
    };
  });

  if (result.length === 0) {
    return undefined;
  }

  return result;
}

export function getTabsFromParams(
  tabsFromParamsValue: string | undefined,
  majorVersions: MajorVersion[]
): Tab[] | undefined {
  if (!tabsFromParamsValue) {
    return undefined;
  }

  const entries = tabsFromParamsValue.split(',');
  if (entries.length === 0) {
    return undefined;
  }

  const tabs: Tab[] = entries.map((entry) => {
    const [id, major, modelId, runId] = entry.split(':');

    let majorVersion: MajorVersion | undefined;
    if (major !== '' && !!major) {
      const majorNumber = parseInt(major);
      majorVersion = majorVersions.find((version) => version.major === majorNumber);
    }

    return {
      id,
      majorVersion: majorVersion,
      modelId: modelId === '' ? undefined : modelId,
      runId: runId === '' ? undefined : runId,
    };
  });

  const fixedTabs = fixInvalidTabs(tabs);
  if (!fixedTabs || fixedTabs.length === 0) {
    return undefined;
  }

  return fixedTabs;
}

export function getParamFromTabs(tabs: Tab[] | undefined): string | undefined {
  if (!tabs) {
    return undefined;
  }

  const fixedTabs = fixInvalidTabs(tabs);
  if (!fixedTabs || fixedTabs.length === 0) {
    return undefined;
  }

  return fixedTabs
    .map((tab) => `${tab.id}:${tab.majorVersion?.major ?? ''}:${tab.modelId ?? ''}:${tab.runId ?? ''}`)
    .join(',');
}
