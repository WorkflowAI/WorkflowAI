import { useCallback } from 'react';
import { useCopyToClipboard } from 'usehooks-ts';
import { displaySuccessToaster } from '@/components/ui/Sonner';
import { TenantID } from '@/types/aliases';
import { staticRunURL } from '../routeFormatter';

type TCopyOptions = {
  successMessage?: string;
};

export function useCopy() {
  const [, copy] = useCopyToClipboard();
  return useCallback(
    (text: string, options?: TCopyOptions) => {
      const successMessage = options?.successMessage ?? 'Copied to clipboard';
      copy(text);
      displaySuccessToaster(successMessage);
    },
    [copy]
  );
}

export function useCopyCurrentUrl() {
  const copy = useCopy();
  return useCallback(() => {
    copy(window.location.href, {
      successMessage: 'Page link copied to clipboard',
    });
  }, [copy]);
}

export function useCopyRunURL(tenant: TenantID | undefined, taskId: string | undefined, runId: string | undefined) {
  const copy = useCopy();
  return useCallback(() => {
    if (!taskId || !runId) {
      return;
    }

    copy(staticRunURL(tenant, taskId, runId), {
      successMessage: 'Run URL copied to clipboard',
    });
  }, [copy, tenant, taskId, runId]);
}
