'use client';

import { useCallback, useState } from 'react';
import { useOrFetchOrganizationSettings } from '@/store';
import { useOrganizationSettings } from '@/store/organization_settings';
import { AI_PROVIDERS_METADATA } from '../AIModelsCombobox/utils';
import { AddProviderKeyModal } from './AddProviderKeyModal';
import { ProviderKeyManagementItem } from './ProviderKeyManagementItem';

export function ManageProviderKeysContainer() {
  const [currentProvider, setCurrentProvider] = useState<string | null | undefined>(null);
  const onCloseAddProviderKeyModal = useCallback(() => {
    setCurrentProvider(null);
  }, [setCurrentProvider]);

  const addProviderConfig = useOrganizationSettings((state) => state.addProviderConfig);

  const deleteProviderConfig = useOrganizationSettings((state) => state.deleteProviderConfig);

  const { organizationSettings } = useOrFetchOrganizationSettings();

  return (
    <div className='p-0 gap-0 flex flex-col'>
      <div className='flex flex-col gap-3.5 px-4 py-3.5 border-b border-gray-200 border-dashed'>
        <div className='text-[16px] font-semibold text-gray-900'>Manage Provider Keys</div>
        <div className='text-gray-900 text-[12px] font-normal'>Configure your API keys for specific providers.</div>
        <div className='text-gray-900 text-[12px] font-normal'>
          The provided API keys will be used first, however WorkflowAI’s keys may be used as a backup if yours hit a
          rate limit.
        </div>
      </div>

      <div className='p-0 flex flex-col overflow-y-auto px-4'>
        {Object.entries(AI_PROVIDERS_METADATA).map(([provider, metadata]) => (
          <ProviderKeyManagementItem
            key={metadata.name}
            settingsProviders={organizationSettings?.providers}
            provider={provider}
            providerMetadata={metadata}
            setCurrentProvider={setCurrentProvider}
            deleteProviderConfig={deleteProviderConfig}
          />
        ))}
      </div>

      <AddProviderKeyModal
        open={!!currentProvider}
        onClose={onCloseAddProviderKeyModal}
        currentProvider={currentProvider}
        organizationSettings={organizationSettings}
        addProviderConfig={addProviderConfig}
      />
    </div>
  );
}
