'use client';

import { ManageProviderKeysContainer } from '@/components/ProviderKeysModal/ManageProviderKeysContainer';

export default function ProvidersPage() {
  return (
    <div className='flex w-full h-full items-center justify-center bg-custom-gradient-1'>
      <ManageProviderKeysContainer />
    </div>
  );
}
