import { AdvancedSettings } from '../../hooks/useProxyPlaygroundSearchParams';
import { advencedSettingNameFromKey } from '../../utils';

type Props = {
  advancedSettings: AdvancedSettings;
};

export function AdvancedSettingsPreviewLabel(props: Props) {
  const { advancedSettings } = props;

  const nonEmptySettings: [string, string][] = [];
  for (const [key, value] of Object.entries(advancedSettings)) {
    if (value !== undefined && typeof value === 'string' && key !== 'temperature') {
      const name = advencedSettingNameFromKey(key);
      nonEmptySettings.push([name, value]);
    }
  }

  return (
    <div className='flex w-max items-center justify-end h-5 max-h-5 gap-2 whitespace-nowrap'>
      {nonEmptySettings.map(([name, value]) => (
        <div key={name} className='text-gray-500 text-[12px] shrink-0'>
          {name}: <span className='font-semibold text-gray-700'>{value}</span>
        </div>
      ))}
    </div>
  );
}
