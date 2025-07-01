import { AI_PROVIDERS_METADATA } from '@/components/AIModelsCombobox/utils';
import { cn } from '@/lib/utils/cn';
import { Provider } from '@/types/workflowAI';
import { MysteryModelIcon } from './mysteryModelIcon';

type AIProviderIconProps = {
  providerId?: string | null | undefined;
  name?: string;
  fallbackOnMysteryIcon?: boolean;
  sizeClassName?: string;
};

export function AIProviderIcon(props: AIProviderIconProps) {
  const { providerId, fallbackOnMysteryIcon, name, sizeClassName = 'w-5 h-5' } = props;

  if (!!name) {
    const provider = Object.values(AI_PROVIDERS_METADATA).find((provider) => provider.name === name);

    if (provider) {
      return <div className={cn('flex items-center justify-center', sizeClassName)}>{provider.icon}</div>;
    }
  }

  const icon = AI_PROVIDERS_METADATA[providerId as Provider]?.icon;
  if (icon === undefined && !fallbackOnMysteryIcon) {
    return null;
  }

  return <div className={cn('flex items-center justify-center', sizeClassName)}>{icon || <MysteryModelIcon />}</div>;
}

type AIProviderSVGIconProps = {
  providerId: string | null | undefined;
};

export function AIProviderSVGIcon(props: AIProviderSVGIconProps) {
  const { providerId } = props;

  const icon = AI_PROVIDERS_METADATA[providerId as Provider]?.icon;

  return icon;
}
