'use client';

import { ApiKeysModal } from '@/components/ApiKeysModal/ApiKeysModal';
import { CommandK } from '@/components/CommandK';
import { TaskSettingsModal } from '@/components/TaskSettingsModal/TaskSettingsModal';
import { StripeWrapper } from '@/components/stripe/StripeWrapper';
import { useAuth } from '@/lib/AuthContext';
import { useTaskParams, useTenantID } from '@/lib/hooks/useTaskParams';
import { TENANT_PLACEHOLDER } from '@/lib/routeFormatter';
import { useOrFetchTask } from '@/store';
import { LandingPage } from '../landing/LandingPage';
import { looksLikeURL } from '../landing/sections/SuggestedFeatures/utils';
import { LoggedOutBanner, LoggedOutBannerForDemoTask } from './components/LoggedOutBanner';
import { RedirectForTenant } from './components/RedirectForTenant';
import { Sidebar } from './components/sidebar';

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  const tenant = useTenantID();

  const { taskId, tenant: tenantParam } = useTaskParams();
  const { isSignedIn } = useAuth();
  const { task } = useOrFetchTask(tenant, taskId);

  const showTaskBanner = !isSignedIn && tenant === TENANT_PLACEHOLDER && !!taskId;

  const showBanner = !showTaskBanner && !isSignedIn;

  // Split the tenant into parts and check if the first part is a URL
  const parts = tenantParam.split('/');
  const firstPart = parts[0];

  if (looksLikeURL(firstPart)) {
    return <LandingPage companyURL={firstPart} />;
  }

  return (
    <RedirectForTenant>
      <StripeWrapper>
        <ApiKeysModal />
        <div className='flex flex-col h-full max-h-screen overflow-hidden bg-custom-gradient-1'>
          {showBanner && <LoggedOutBanner />}
          {showTaskBanner && <LoggedOutBannerForDemoTask name={task?.name ?? taskId} />}
          <div className='flex-1 flex overflow-hidden'>
            <Sidebar />
            <CommandK tenant={tenant} />
            <div className='flex-1 overflow-y-auto'>{children}</div>
            <TaskSettingsModal />
          </div>
        </div>
      </StripeWrapper>
    </RedirectForTenant>
  );
}
