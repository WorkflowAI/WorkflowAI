'use client';

import { ApiKeysModal } from '@/components/ApiKeysModal/ApiKeysModal';
import { CommandK } from '@/components/CommandK';
import { TaskSettingsModal } from '@/components/TaskSettingsModal/TaskSettingsModal';
import { StripeWrapper } from '@/components/stripe/StripeWrapper';
import { useAuth } from '@/lib/AuthContext';
import { useTaskParams, useTenantID } from '@/lib/hooks/useTaskParams';
import { TENANT_PLACEHOLDER } from '@/lib/routeFormatter';
import { useOrFetchTask } from '@/store';
import { looksLikeURL } from '../landing/sections/SuggestedFeatures/utils';
import { LoggedOutBanner, LoggedOutBannerForDemoTask } from './components/LoggedOutBanner';
import { MigrationBanner } from './components/MigrationBanner';
import { ModelBanner } from './components/ModelBanner';
import { PaymentBanner } from './components/PaymentBanner';
import { RedirectForTenant } from './components/RedirectForTenant';
import { Sidebar } from './components/sidebar';
import { useModelToAdvertise } from './components/useModelToAdvertise';
import { usePaymentBanners } from './components/usePaymentBanners';

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  const tenant = useTenantID();

  const { taskId, tenant: tenantParam } = useTaskParams();
  const { isSignedIn, tenantSlug } = useAuth();
  const { task } = useOrFetchTask(tenant, taskId);

  const showTaskBanner = !isSignedIn && tenant === TENANT_PLACEHOLDER && !!taskId;

  const { modelsToAdvertise, dismiss } = useModelToAdvertise();
  const { state: paymentBannerState } = usePaymentBanners(isSignedIn, tenantSlug);

  const showBanner = !showTaskBanner && !isSignedIn;

  // Split the tenant into parts and check if the first part is a URL
  const parts = tenantParam.split('/');
  const firstPart = parts[0];

  if (looksLikeURL(firstPart)) {
    return children;
  }

  return (
    <RedirectForTenant>
      <StripeWrapper>
        <ApiKeysModal />
        <div className='flex flex-col h-full max-h-screen overflow-hidden bg-custom-gradient-1'>
          <MigrationBanner tenant={tenant} />
          {showBanner && <LoggedOutBanner />}
          {showTaskBanner && <LoggedOutBannerForDemoTask name={task?.name ?? taskId} />}
          {!!modelsToAdvertise && !paymentBannerState && <ModelBanner models={modelsToAdvertise} onClose={dismiss} />}
          {!!paymentBannerState && <PaymentBanner state={paymentBannerState} />}
          <div className='flex flex-1 sm:flex-row flex-col overflow-hidden'>
            <Sidebar />
            <CommandK tenant={tenant} />
            <div className='flex flex-1 overflow-hidden'>{children}</div>
            <TaskSettingsModal />
          </div>
        </div>
      </StripeWrapper>
    </RedirectForTenant>
  );
}
