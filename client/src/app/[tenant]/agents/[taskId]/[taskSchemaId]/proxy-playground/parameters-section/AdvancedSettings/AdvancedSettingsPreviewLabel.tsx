import { AdvancedSettings } from '../../hooks/useProxyPlaygroundSearchParams';
import {
  advencedSettingNameFromKey,
  advencedSettingsVersionPropertiesKeys,
  defaultValueForAdvencedSetting,
} from '../../utils';

type Props = {
  advancedSettings: AdvancedSettings;
};

export function AdvancedSettingsPreviewLabel(props: Props) {
  const { advancedSettings } = props;

  const settings: [string, string][] = [];

  for (const key of advencedSettingsVersionPropertiesKeys) {
    const value = (advancedSettings as unknown as { [K in typeof key]: string | undefined })[key];
    const name = advencedSettingNameFromKey(key);
    const valueToUse = value ?? defaultValueForAdvencedSetting(key) ?? 'Not Set';
    if (valueToUse !== undefined) {
      settings.push([name, valueToUse]);
    }
  }

  return (
    <div className='flex w-max items-center justify-end h-5 max-h-5 gap-2 whitespace-nowrap'>
      {settings.map(([name, value]) => (
        <div key={name} className='text-gray-500 text-[12px] shrink-0'>
          {name}: <span className='font-semibold text-gray-700 capitalize'>{value}</span>
        </div>
      ))}
    </div>
  );
}
