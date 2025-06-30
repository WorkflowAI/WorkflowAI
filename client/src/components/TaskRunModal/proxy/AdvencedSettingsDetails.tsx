import { ChevronDownIcon, ChevronUpIcon } from 'lucide-react';
import { useState } from 'react';
import { defaultValueForAdvencedSetting } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/utils';
import { cn } from '@/lib/utils';
import { MajorVersionProperties, OpenAIProxyToolChoice, VersionV1 } from '@/types/workflowAI';
import { ProxyRunDetailsParameterEntry } from './ProxyRunDetailsParameterEntry';

type AdvencedSettingsDetailsEntryProps = {
  title: string;
  value: string | number | boolean | undefined | null | string[] | OpenAIProxyToolChoice;
  borderColor?: string;
};

export function AdvencedSettingsDetailsEntry(props: AdvencedSettingsDetailsEntryProps) {
  const { title, value, borderColor } = props;

  const renderValue = () => {
    if (value === null || value === undefined) {
      return '';
    }
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    if (typeof value === 'object') {
      return JSON.stringify(value);
    }
    return value.toString();
  };

  return (
    <ProxyRunDetailsParameterEntry title={title} className={cn('border-b', borderColor)}>
      <div className='border border-gray-200 rounded-[2px] px-2 py-0.5 text-[13px] text-gray-700'>{renderValue()}</div>
    </ProxyRunDetailsParameterEntry>
  );
}

type Props = {
  version?: VersionV1;
  majorVersionProperties?: MajorVersionProperties;
  style: 'table' | 'single';
  borderColor?: string;
};

export function AdvencedSettingsDetails(props: Props) {
  const { version, majorVersionProperties, style, borderColor = 'border-gray-100' } = props;

  const max_tokens =
    version?.properties.max_tokens ??
    majorVersionProperties?.max_tokens ??
    defaultValueForAdvencedSetting('max_tokens');

  const top_p = version?.properties.top_p ?? majorVersionProperties?.top_p ?? defaultValueForAdvencedSetting('top_p');

  const presence_penalty =
    version?.properties.presence_penalty ??
    majorVersionProperties?.presence_penalty ??
    defaultValueForAdvencedSetting('presence_penalty');

  const frequency_penalty =
    version?.properties.frequency_penalty ??
    majorVersionProperties?.frequency_penalty ??
    defaultValueForAdvencedSetting('frequency_penalty');

  const tool_choice =
    version?.properties.tool_choice ??
    majorVersionProperties?.tool_choice ??
    defaultValueForAdvencedSetting('tool_choice');

  const [open, setOpen] = useState(false);

  return (
    <div className='flex flex-col w-full'>
      <div
        className={cn(
          'flex flex-row w-full items-center gap-2 justify-between py-2.5 cursor-pointer',
          style === 'table' ? 'px-4 border-b border-gray-100' : ''
        )}
        onClick={() => setOpen(!open)}
      >
        <div className='text-[13px] text-gray-900'>Advanced Settings</div>
        {open ? (
          <ChevronUpIcon className='w-4 h-4 text-gray-900' />
        ) : (
          <ChevronDownIcon className='w-4 h-4 text-gray-900' />
        )}
      </div>
      {open && (
        <div
          className={cn(
            'flex flex-col w-full',
            style === 'single' ? 'bg-white border-t border-l border-r' : '',
            borderColor
          )}
        >
          <div
            className={cn(
              'grid grid-cols-[repeat(auto-fit,minmax(max(160px,50%),1fr))] [&>*:nth-child(odd)]:border-r',
              borderColor
            )}
          >
            <AdvencedSettingsDetailsEntry
              title='Max Tokens'
              value={max_tokens ?? 'Not Set'}
              borderColor={borderColor}
            />
            <AdvencedSettingsDetailsEntry title='Top P' value={top_p ?? 'Not Set'} borderColor={borderColor} />
            <AdvencedSettingsDetailsEntry
              title='Presence Penalty'
              value={presence_penalty ?? 'Not Set'}
              borderColor={borderColor}
            />
            <AdvencedSettingsDetailsEntry
              title='Frequency Penalty'
              value={frequency_penalty ?? 'Not Set'}
              borderColor={borderColor}
            />
          </div>
          <AdvencedSettingsDetailsEntry
            title='Tool Choice'
            value={tool_choice ?? 'Not Set'}
            borderColor={borderColor}
          />
        </div>
      )}
    </div>
  );
}
