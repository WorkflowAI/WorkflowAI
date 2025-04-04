import { DeleteFilled } from '@fluentui/react-icons';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { useCallback, useMemo } from 'react';
import { ProviderSettings } from '@/types/workflowAI';
import { AIProviderMetadata } from '../AIModelsCombobox/utils';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { SimpleTooltip } from '../ui/Tooltip';

dayjs.extend(relativeTime);

type ProviderKeyManagementItemActionsProps = {
  onAddProviderKey: () => void;
  onDeleteKey: () => Promise<void>;

  settingsProvider: ProviderSettings | undefined;
};

function ProviderKeyManagementItemActions(props: ProviderKeyManagementItemActionsProps) {
  const { settingsProvider, onAddProviderKey, onDeleteKey } = props;

  if (!settingsProvider) {
    return (
      <Button variant='newDesign' onClick={onAddProviderKey}>
        Add
      </Button>
    );
  }

  return (
    <div className='flex gap-3 items-center'>
      <div className='text-[13px] text-gray-700'>{`Added ${dayjs(settingsProvider.created_at).fromNow()}`}</div>
      <Button variant='destructive' size='none' onClick={onDeleteKey} fluentIcon={DeleteFilled} className='w-8 h-8' />
    </div>
  );
}

type ProviderKeyManagementItemProps = {
  provider: string;
  providerMetadata: AIProviderMetadata;
  settingsProviders: ProviderSettings[] | undefined;
  setCurrentProvider: (provider: string) => void;
  deleteProviderConfig: (providerId: string) => Promise<void>;
};

export function ProviderKeyManagementItem(props: ProviderKeyManagementItemProps) {
  const { provider, providerMetadata, settingsProviders, setCurrentProvider, deleteProviderConfig } = props;

  const settingsProvider = useMemo(
    () => settingsProviders?.find((p) => p.provider === provider),
    [settingsProviders, provider]
  );

  const onAddProviderKey = useCallback(() => {
    setCurrentProvider(provider);
  }, [setCurrentProvider, provider]);

  const onDeleteKey = useCallback(async () => {
    if (!settingsProvider?.id) return;
    await deleteProviderConfig(settingsProvider.id);
  }, [deleteProviderConfig, settingsProvider]);

  return (
    <div className='flex gap-2 items-center py-2 border-b last:border-b-0 justify-between'>
      <div className='flex gap-4 items-center'>
        <div className='w-10 h-10 rounded-[2px] bg-white border border-gray-100 flex items-center justify-center'>
          {providerMetadata.icon}
        </div>
        <div className='text-[13px] text-gray-900 font-semibold'>{providerMetadata.name}</div>
      </div>
      <ProviderKeyManagementItemActions
        settingsProvider={settingsProvider}
        onAddProviderKey={onAddProviderKey}
        onDeleteKey={onDeleteKey}
      />
    </div>
  );
}
