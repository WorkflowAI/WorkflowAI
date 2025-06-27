import { useMemo } from 'react';
import { ProxyMessage } from '@/types/workflowAI';
import { MajorVersion } from '@/types/workflowAI';
import { removeIdsFromMessages } from '../proxy-messages/utils';
import { defaultValueForAdvencedSetting, parseValidNumber, valueFromToolChoice } from '../utils';
import { AdvancedSettings } from './useProxyPlaygroundSearchParams';

function proxyMessagesValue(proxyMessages: ProxyMessage[] | undefined) {
  if (proxyMessages) {
    return JSON.stringify(proxyMessages);
  }
  return undefined;
}

type Props = {
  majorVersions: MajorVersion[];
  userSelectedMajor: number | undefined;
  proxyMessages: ProxyMessage[] | undefined;
  advancedSettings: AdvancedSettings;
};

export function useProxyMatchVersion(props: Props) {
  const { majorVersions, advancedSettings, proxyMessages, userSelectedMajor } = props;

  const stringifiedProxyMessages = useMemo(() => {
    const cleanedProxyMessages = proxyMessages ? removeIdsFromMessages(proxyMessages) : undefined;
    return proxyMessagesValue(cleanedProxyMessages);
  }, [proxyMessages]);

  const matchedVersion = useMemo(() => {
    const matchingVersions = majorVersions.filter((version) => {
      const candidateProxyMessagesValue = proxyMessagesValue(version.properties.messages || undefined);

      const numberTemperature = parseValidNumber(
        advancedSettings.temperature ?? defaultValueForAdvencedSetting('temperature')
      );

      const numberTopP = parseValidNumber(advancedSettings.top_p ?? defaultValueForAdvencedSetting('top_p'));

      const numberFrequencyPenalty = parseValidNumber(
        advancedSettings.frequency_penalty ?? defaultValueForAdvencedSetting('frequency_penalty')
      );

      const numberPresencePenalty = parseValidNumber(
        advancedSettings.presence_penalty ?? defaultValueForAdvencedSetting('presence_penalty')
      );

      const toolChoice = advancedSettings.tool_choice ?? defaultValueForAdvencedSetting('tool_choice');

      const versionToolChoiceValue = valueFromToolChoice(version.properties.tool_choice);

      return (
        version.properties.temperature === numberTemperature &&
        version.properties.top_p === numberTopP &&
        version.properties.frequency_penalty === numberFrequencyPenalty &&
        version.properties.presence_penalty === numberPresencePenalty &&
        versionToolChoiceValue === toolChoice &&
        candidateProxyMessagesValue === stringifiedProxyMessages
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
  }, [majorVersions, advancedSettings, userSelectedMajor, stringifiedProxyMessages]);

  return { matchedVersion };
}
