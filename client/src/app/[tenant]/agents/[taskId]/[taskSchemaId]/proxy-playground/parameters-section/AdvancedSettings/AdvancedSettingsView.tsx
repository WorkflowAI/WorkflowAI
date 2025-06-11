import { ChevronDown12Regular, ChevronUp12Regular } from '@fluentui/react-icons';
import { useState } from 'react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/Popover';
import { AdvancedSettings } from '../../hooks/useProxyPlaygroundSearchParams';
import { advencedSettingNameFromKey, defaultValueForAdvencedSetting } from '../../utils';
import { AdvancedSettingsCacheEntry } from './AdvancedSettingsCacheEntry';
import { AdvancedSettingsPreviewLabel } from './AdvancedSettingsPreviewLabel';
import { AdvancedSettingsSliderEntry } from './AdvancedSettingsSliderEntry';
import { AdvancedSettingsSwitchEntry } from './AdvancedSettingsSwitchEntry';
import { AdvancedSettingsTextEntry } from './AdvancedSettingsTextEntry';

type Props = {
  advancedSettings: AdvancedSettings;
};

export function AdvancedSettingsView(props: Props) {
  const { advancedSettings } = props;

  const [isAdvancedSettingsOpen, setIsAdvancedSettingsOpen] = useState(false);

  return (
    <div className='flex flex-col gap-2.5 w-full items-center justify-end overflow-hidden'>
      <div className='flex w-full justify-end overflow-hidden pr-3'>
        <div className='relative flex max-w-full justify-start'>
          <div className='flex w-full justify-start overflow-x-auto scrollbar-hide px-2'>
            <AdvancedSettingsPreviewLabel advancedSettings={advancedSettings} />
          </div>
          <div className='pointer-events-none absolute inset-y-0 left-0 w-2 bg-gradient-to-r from-[#fef9fa] to-transparent' />
          <div className='pointer-events-none absolute inset-y-0 right-0 w-2 bg-gradient-to-l from-[#fef9fa] to-transparent' />
        </div>
      </div>
      <div className='flex w-full justify-end pr-4'>
        <Popover open={isAdvancedSettingsOpen} onOpenChange={setIsAdvancedSettingsOpen}>
          <PopoverTrigger asChild>
            <div
              className='flex flex-row gap-0.5 items-center cursor-pointer'
              onClick={() => setIsAdvancedSettingsOpen(!isAdvancedSettingsOpen)}
            >
              <div className='text-gray-700 hover:text-gray-500 text-[12px] font-semibold underline'>
                Advanced Settings
              </div>
              {isAdvancedSettingsOpen ? (
                <ChevronUp12Regular className='w-3 h-3 text-gray-700' />
              ) : (
                <ChevronDown12Regular className='w-3 h-3 text-gray-700' />
              )}
            </div>
          </PopoverTrigger>
          <PopoverContent
            className='w-[316px] p-0 rounded-[2px] overflow-y-auto border border-gray-300 shadow-lg max-h-[320px]'
            align='end'
            side='bottom'
            sideOffset={5}
          >
            <div className='flex flex-col w-full h-max'>
              <AdvancedSettingsCacheEntry
                name={advencedSettingNameFromKey('cache')}
                value={advancedSettings.cache}
                setValue={advancedSettings.setCache}
                defaultValue={defaultValueForAdvencedSetting('cache')}
                className='border-b border-gray-100'
                prompt='Auto: if a previous run exists with the same version and input, and if the temperature is 0, the cached output is returned. Always: the cached output is returned when available, regardless of the temperature value. Never: the cache is never used.'
              />

              <AdvancedSettingsSliderEntry
                name={advencedSettingNameFromKey('top_p')}
                value={advancedSettings.topP}
                setValue={advancedSettings.setTopP}
                defaultValue={defaultValueForAdvencedSetting('top_p')}
                minValue={0.01}
                maxValue={1}
                isOptional={false}
                className='border-b border-gray-100'
                prompt='Optional number between 0 and 1 (exclusive of 0, defaults to 1). Controls nucleus sampling by limiting the model to the smallest set of likely tokens whose combined probability is ≥ top_p. Ignored if temperature is set.'
                step={0.01}
              />
              <AdvancedSettingsSliderEntry
                name={advencedSettingNameFromKey('max_tokens')}
                value={advancedSettings.maxTokens}
                setValue={advancedSettings.setMaxTokens}
                defaultValue={defaultValueForAdvencedSetting('max_tokens')}
                minValue={1}
                maxValue={4096}
                isOptional={true}
                allowGoingAboveMaxValue={true}
                className='border-b border-gray-100'
                prompt='Optional integer greater than 0. Sets the maximum number of tokens the model can generate in its response. If not set, the model will use its full available limit.'
                step={1}
              />
              <AdvancedSettingsSwitchEntry
                name={advencedSettingNameFromKey('stream')}
                value={advancedSettings.stream}
                setValue={advancedSettings.setStream}
                className='border-b border-gray-100'
                prompt='Optional boolean. If true, the response is returned as a stream of chunks instead of waiting for the full output. Defaults to false.'
              />
              <AdvancedSettingsSwitchEntry
                name='Stream Options: Include Usage'
                value={advancedSettings.streamOptionsIncludeUsage}
                setValue={advancedSettings.setStreamOptionsIncludeUsage}
                className='border-b border-gray-100'
                prompt='Optional boolean. When stream is true, this includes token usage details in the final streamed message.'
              />
              <AdvancedSettingsTextEntry
                name={advencedSettingNameFromKey('stop')}
                value={advancedSettings.stop}
                setValue={advancedSettings.setStop}
                className='border-b border-gray-100'
                prompt='Optional string or array of up to 4 strings. The model stops generating once it encounters any of these sequences.'
              />
              <AdvancedSettingsSliderEntry
                name={advencedSettingNameFromKey('presence_penalty')}
                value={advancedSettings.presencePenalty}
                setValue={advancedSettings.setPresencePenalty}
                defaultValue={defaultValueForAdvencedSetting('presence_penalty')}
                minValue={-2}
                maxValue={2}
                isOptional={false}
                className='border-b border-gray-100'
                prompt='Optional number between -2 and 2. Positive values discourage the model from repeating tokens that already appeared in the prompt.'
                step={0.01}
              />
              <AdvancedSettingsSliderEntry
                name={advencedSettingNameFromKey('frequency_penalty')}
                value={advancedSettings.frequencyPenalty}
                setValue={advancedSettings.setFrequencyPenalty}
                defaultValue={defaultValueForAdvencedSetting('frequency_penalty')}
                minValue={-2}
                maxValue={2}
                isOptional={false}
                className='border-b border-gray-100'
                prompt='Optional number between -2 and 2. Positive values reduce the likelihood of tokens being repeated in proportion to how often they already appear.'
                step={0.01}
              />
              <AdvancedSettingsTextEntry
                name={advencedSettingNameFromKey('tool_choice')}
                value={advancedSettings.toolChoice}
                setValue={advancedSettings.setToolChoice}
                prompt='Optional value that can be "none", "auto", or an object specifying a function. Controls whether the model uses tools or calls a specific function.'
              />
            </div>
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );
}
