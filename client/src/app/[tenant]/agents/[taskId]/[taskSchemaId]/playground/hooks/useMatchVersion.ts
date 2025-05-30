import { useMemo } from 'react';
import { MajorVersion, ProxyMessage } from '@/types/workflowAI';
import { removeIdsFromMessages } from '../../proxy-playground/proxy-messages/utils';

function proxyMessagesValue(proxyMessages: ProxyMessage[] | undefined) {
  if (proxyMessages) {
    return JSON.stringify(proxyMessages);
  }
  return undefined;
}

type Props = {
  majorVersions: MajorVersion[];
  temperature: number | undefined;
  instructions: string | undefined;
  proxyMessages: ProxyMessage[] | undefined;
  variantId: string | undefined;
  userSelectedMajor: number | undefined;
  skipCheckingVariantId?: boolean;
  skipCheckingProxyMessages?: boolean;
};

export function useMatchVersion(props: Props) {
  const {
    majorVersions,
    temperature,
    instructions,
    proxyMessages,
    variantId,
    userSelectedMajor,
    skipCheckingVariantId = false,
    skipCheckingProxyMessages = false,
  } = props;

  const stringifiedProxyMessages = useMemo(() => {
    const cleanedProxyMessages = proxyMessages ? removeIdsFromMessages(proxyMessages) : undefined;
    return proxyMessagesValue(cleanedProxyMessages);
  }, [proxyMessages]);

  const matchedVersion = useMemo(() => {
    const matchingVersions = majorVersions.filter((version) => {
      const normalizedVersionInstructions = version.properties.instructions?.toLowerCase().trim() || '';

      const normalizedInstructions = instructions?.toLowerCase().trim() || '';
      const candidateProxyMessagesValue = proxyMessagesValue(version.properties.messages || undefined);

      return (
        version.properties.temperature === temperature &&
        normalizedVersionInstructions === normalizedInstructions &&
        (skipCheckingVariantId || version.properties.task_variant_id === variantId) &&
        (skipCheckingProxyMessages || candidateProxyMessagesValue === stringifiedProxyMessages)
      );
    });

    const allMatchedVersions = matchingVersions.sort((a, b) => b.major - a.major);

    if (userSelectedMajor !== undefined) {
      const result = allMatchedVersions.find((version) => version.major === userSelectedMajor);

      if (result !== undefined) {
        return result;
      }

      return allMatchedVersions[0];
    }

    return allMatchedVersions[0];
  }, [
    majorVersions,
    temperature,
    instructions,
    userSelectedMajor,
    variantId,
    stringifiedProxyMessages,
    skipCheckingVariantId,
    skipCheckingProxyMessages,
  ]);

  return { matchedVersion };
}
