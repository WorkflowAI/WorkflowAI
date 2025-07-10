import { useOrganizationSettings } from '@/store/organization_settings';
import { TenantID } from '@/types/aliases';

export enum PaymentBannerType {
  FIX_PAYMENT = 'FIX_PAYMENT',
  ADD_CREDITS = 'ADD_CREDITS',
}

export function usePaymentBanners(isSignedIn: boolean, tenantSlug: TenantID | undefined) {
  const organizationSettings = useOrganizationSettings((state) =>
    tenantSlug ? state.settingsForTenant[tenantSlug] : undefined
  );
  const lowCreditsMode = !!organizationSettings?.current_credits_usd && organizationSettings.current_credits_usd <= 5;
  const paymentFailure = !!organizationSettings?.payment_failure;

  if (!isSignedIn) {
    return {
      state: undefined,
    };
  }

  if (lowCreditsMode) {
    return {
      state: PaymentBannerType.ADD_CREDITS,
    };
  }

  if (paymentFailure) {
    return {
      state: PaymentBannerType.FIX_PAYMENT,
    };
  }

  return {
    state: undefined,
  };
}
