import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSessionStorage } from 'usehooks-ts';
import { Dialog, DialogContent, DialogTrigger } from '@/components/ui/Dialog';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { useAuth } from '@/lib/AuthContext';
import { STRIPE_PUBLISHABLE_KEY } from '@/lib/constants';
import { useParsedSearchParams, useRedirectWithParams } from '@/lib/queryString';
import { useOrFetchPayments, usePayments } from '@/store/payments';
import { TenantData } from '@/types/workflowAI';
import { ManageCardsContent } from './ManageCardsContent';
import { ManageCardsTooltipContent } from './ManageCardsTooltipContent';
import { useStripePayments } from './hooks/useStripePayments';

type ManageCardsProps = {
  children: React.ReactNode;
  organizationSettings: TenantData | undefined;
};

function ManageCardsInner(props: ManageCardsProps) {
  const { children, organizationSettings } = props;

  const { manageCards: manageCardsValue } = useParsedSearchParams('manageCards');
  const redirectWithParams = useRedirectWithParams();

  const isOpen = useMemo(() => {
    return manageCardsValue === 'true';
  }, [manageCardsValue]);

  const setIsOpen = useCallback(
    (isOpen: boolean) => {
      redirectWithParams({
        params: {
          manageCards: isOpen ? 'true' : undefined,
        },
      });
    },
    [redirectWithParams]
  );

  const { paymentMethod, isInitialized } = useOrFetchPayments();

  const balance = organizationSettings?.current_credits_usd;
  const isPaymentMethodAvailable = !!paymentMethod?.payment_method_id;

  const automaticPaymentsAreSet = organizationSettings?.automatic_payment_enabled;

  const automaticPaymentsFailure = organizationSettings?.payment_failure?.failure_reason;

  const { user } = useAuth();
  const userId = user?.id;

  const [dismissForcedTooltipNoPaymentMethod, setDismissForcedTooltipNoPaymentMethod] = useSessionStorage(
    `dismissForcedTooltipNoPaymentMethod-${userId}`,
    false
  );

  const [dismissForcedTooltipPaymentsFailed, setDismissForcedTooltipPaymentsFailed] = useSessionStorage(
    `dismissForcedTooltipPaymentsFailed-${userId}`,
    false
  );

  const shouldForceTooltipBecauseNoPaymentMethod =
    !isPaymentMethodAvailable && isInitialized && !dismissForcedTooltipNoPaymentMethod;

  const shouldForceTooltipBecausePaymentsFailed =
    !!automaticPaymentsFailure && isInitialized && !dismissForcedTooltipPaymentsFailed;

  const [showAddPaymentMethod, setShowAddPaymentMethod] = useState(false);
  const [showEnableAutoRecharge, setShowEnableAutoRecharge] = useState(false);
  const [amountToAdd, setAmountToAdd] = useState<number | undefined>(undefined);

  const isAddCreditsButtonActive =
    !!amountToAdd && !!paymentMethod?.payment_method_id && amountToAdd >= 5 && amountToAdd <= 5000;

  const reset = useCallback(() => {
    setShowAddPaymentMethod(false);
    setShowEnableAutoRecharge(false);
    setAmountToAdd(undefined);
  }, []);

  useEffect(() => {
    if (isOpen) {
      reset();
    }
  }, [isOpen, reset]);

  const shouldForceTooltip = shouldForceTooltipBecauseNoPaymentMethod || shouldForceTooltipBecausePaymentsFailed;

  const tooltipText = useMemo(() => {
    if (!isPaymentMethodAvailable) {
      return 'Payment method missing.\n\nTap the Credits section to add one\nand so you can continue using\nWorkflowAI once your free credits\nare used.';
    }

    if (automaticPaymentsFailure) {
      return `Auto Recharge failed:\n${automaticPaymentsFailure}\n\nYou may run out of credits soon.\n\nTap the Credits section to update\nyour payment method.`;
    }

    if (automaticPaymentsAreSet) {
      return 'Auto recharge is ON.\n\nTap to view and manage billing details';
    }

    return 'Auto recharge is OFF.\n\nTap to view and manage billing details';
  }, [isPaymentMethodAvailable, automaticPaymentsFailure, automaticPaymentsAreSet]);

  const { addCredits } = useStripePayments();
  const deletePaymentMethod = usePayments((state) => state.deletePaymentMethod);

  const onAddCredits = useCallback(async () => {
    if (!amountToAdd) {
      return;
    }
    const result = await addCredits(amountToAdd);

    if (result) {
      reset();
      setIsOpen(false);
    }
  }, [addCredits, amountToAdd, reset, setIsOpen]);

  const onDeletePaymentMethod = useCallback(async () => {
    await deletePaymentMethod();
    reset();
  }, [deletePaymentMethod, reset]);

  const onUpdatePaymentMethod = useCallback(async () => {
    await deletePaymentMethod();
    reset();
    setShowAddPaymentMethod(true);
  }, [deletePaymentMethod, reset, setShowAddPaymentMethod]);

  const onDismissForcedTooltip = useCallback(
    (event: React.MouseEvent) => {
      event.stopPropagation();

      if (shouldForceTooltipBecauseNoPaymentMethod) {
        setDismissForcedTooltipNoPaymentMethod(true);
      }

      if (shouldForceTooltipBecausePaymentsFailed) {
        setDismissForcedTooltipPaymentsFailed(true);
      }
    },
    [
      setDismissForcedTooltipNoPaymentMethod,
      setDismissForcedTooltipPaymentsFailed,
      shouldForceTooltipBecauseNoPaymentMethod,
      shouldForceTooltipBecausePaymentsFailed,
    ]
  );

  if (!isInitialized || !organizationSettings) {
    return children;
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger className='cursor-pointer w-full text-left'>
        <SimpleTooltip
          content={
            <ManageCardsTooltipContent
              text={tooltipText}
              showDismiss={shouldForceTooltip}
              onDismiss={onDismissForcedTooltip}
            />
          }
          tooltipDelay={300}
          forceShowing={shouldForceTooltip}
          tooltipClassName='border-none bg-gray-800 text-white ml-2 p-2.5 rounded-[2px] font-normal text-[12px] font-normal'
        >
          {children}
        </SimpleTooltip>
      </DialogTrigger>

      <DialogContent className='max-w-[400px] p-0'>
        <ManageCardsContent
          paymentMethod={paymentMethod}
          isPaymentMethodAvailable={isPaymentMethodAvailable}
          organizationSettings={organizationSettings}
          balance={balance}
          setShowAddPaymentMethod={setShowAddPaymentMethod}
          showAddPaymentMethod={showAddPaymentMethod}
          setIsOpen={setIsOpen}
          onAddCredits={onAddCredits}
          setShowEnableAutoRecharge={setShowEnableAutoRecharge}
          showEnableAutoRecharge={showEnableAutoRecharge}
          amountToAdd={amountToAdd}
          setAmountToAdd={setAmountToAdd}
          isAddCreditsButtonActive={isAddCreditsButtonActive}
          deletePaymentMethod={onDeletePaymentMethod}
          automaticPaymentsFailure={automaticPaymentsFailure}
          onUpdatePaymentMethod={onUpdatePaymentMethod}
        />
      </DialogContent>
    </Dialog>
  );
}

export function ManageCards(props: ManageCardsProps) {
  if (!STRIPE_PUBLISHABLE_KEY) {
    return null;
  }
  return <ManageCardsInner {...props} />;
}
