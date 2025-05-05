import { useCallback, useMemo, useState } from 'react';
import { useParsedSearchParams, useRedirectWithParams } from '@/lib/queryString';
import { MajorVersion } from '@/types/workflowAI';
import { Tab } from './utils';
import { getParamFromTabs, getTabsFromParams } from './utils';

// This hook is used to get the tabs from the params and set them to the params + buffer them to make the update faster
export function useBufferedParamsForTabs(majorVersions: MajorVersion[] | undefined) {
  const redirectWithParams = useRedirectWithParams();
  const { tabs: tabsFromParamsValue } = useParsedSearchParams('tabs');

  const [bufferedTabs, setBufferedTabs] = useState<Tab[] | undefined>(undefined);

  const tabs: Tab[] | undefined = useMemo(() => {
    if (!majorVersions) {
      return undefined;
    }

    const result = getTabsFromParams(tabsFromParamsValue, majorVersions);
    setBufferedTabs(result);
    return result;
  }, [tabsFromParamsValue, majorVersions]);

  const setTabs = useCallback(
    (tabs: Tab[] | undefined) => {
      setBufferedTabs(tabs);

      const tabsParam = getParamFromTabs(tabs);
      redirectWithParams({
        params: { tabs: tabsParam },
        scroll: false,
      });
    },
    [redirectWithParams]
  );

  return { tabs: bufferedTabs, setTabs, tabsFromParams: tabs };
}
