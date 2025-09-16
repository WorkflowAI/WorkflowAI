import { useCallback } from 'react';
import { useParsedSearchParams, useRedirectWithParams } from '@/lib/queryString';

export const NEW_TASK_MODAL_OPEN = 'newTaskModalOpen';
export const NEW_PROXY_AGENT_MODAL_OPEN = 'addAgent';
export const SETUP_MODAL_OPEN = 'setupModalOpen';
export const DEPLOY_ITERATION_MODAL_OPEN = 'deployIterationModalOpen';
export const TASK_SETTINGS_MODAL_OPEN = 'taskSettingsModalOpen';
export const API_KEYS_MODAL_OPEN = 'apiKeysModalOpen';

export function useQueryParamModal<K extends Record<string, string | undefined>>(
  modalName: string,
  extras?: (keyof K)[]
) {
  const { [modalName]: open } = useParsedSearchParams(modalName);
  const redirectWithParams = useRedirectWithParams();

  const openModal = useCallback(
    (extraQueryParams?: K) => {
      redirectWithParams({
        params: { [modalName]: 'true', ...(extraQueryParams ?? {}) },
      });
    },
    [redirectWithParams, modalName]
  );

  const closeModal = useCallback(() => {
    const params: Record<string, undefined> = { [modalName]: undefined };
    if (extras) {
      for (const k of extras) {
        params[k as string] = undefined;
      }
    }
    redirectWithParams({ params });
  }, [modalName, redirectWithParams, extras]);

  return { open: open === 'true', openModal, closeModal };
}
