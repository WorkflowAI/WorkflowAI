import { useCallback, useMemo, useState } from 'react';
import { Switch } from '@/components/ui/Switch';
import { usePayments } from '@/store/payments';
import { TenantID } from '@/types/aliases';
import { TenantData } from '@/types/workflowAI';
import { BottomButtonBar } from './BottomButtonBar';
import { CurrencyInput } from './CurrencyInput';

type EnableAutoRechargeContentProps = {
  organizationSettings: TenantData;
  setIsOpen: (isOpen: boolean) => void;
};

export function EnableAutoRechargeContent(props: EnableAutoRechargeContentProps) {
  const { organizationSettings, setIsOpen } = props;

  const tenantId = organizationSettings.slug as TenantID | undefined;

  const [isOn, setIsOn] = useState<boolean>(organizationSettings.automatic_payment_enabled ?? false);

  const [automaticPaymentThreshold, setAutomaticPaymentThreshold] = useState<number | undefined>(
    organizationSettings.automatic_payment_threshold ?? 10
  );

  const [balanceToMaintain, setBalanceToMaintain] = useState<number | undefined>(
    organizationSettings.automatic_payment_balance_to_maintain ?? 50
  );

  const isSaveActive = useMemo(() => {
    if (!isOn && !organizationSettings.automatic_payment_enabled) {
      return false;
    }

    if (
      isOn === organizationSettings.automatic_payment_enabled &&
      balanceToMaintain === organizationSettings.automatic_payment_balance_to_maintain &&
      automaticPaymentThreshold === organizationSettings.automatic_payment_threshold
    ) {
      return false;
    }

    if (!balanceToMaintain || !automaticPaymentThreshold) {
      return false;
    }

    if (balanceToMaintain < 5 || balanceToMaintain > 5000) {
      return false;
    }

    if (automaticPaymentThreshold < 5 || automaticPaymentThreshold > 5000) {
      return false;
    }

    if (automaticPaymentThreshold >= balanceToMaintain) {
      return false;
    }

    return true;
  }, [
    isOn,
    balanceToMaintain,
    automaticPaymentThreshold,
    organizationSettings.automatic_payment_enabled,
    organizationSettings.automatic_payment_balance_to_maintain,
    organizationSettings.automatic_payment_threshold,
  ]);

  const updateAutomaticPayment = usePayments((state) => state.updateAutomaticPayment);

  const onSaveSettings = useCallback(async () => {
    const thresholdToSend = isOn ? automaticPaymentThreshold ?? null : null;
    const balanceToMaintainToSend = isOn ? balanceToMaintain ?? null : null;

    await updateAutomaticPayment(isOn, thresholdToSend, balanceToMaintainToSend, tenantId);

    setIsOpen(false);
  }, [isOn, automaticPaymentThreshold, balanceToMaintain, updateAutomaticPayment, setIsOpen, tenantId]);

  return (
    <div className='flex flex-col h-full w-full overflow-hidden bg-custom-gradient-1 rounded-[2px]'>
      <div className='text-[16px] font-semibold text-gray-900 px-4 py-3.5 border-b border-gray-200 border-dashed'>
        Auto Recharge Settings
      </div>

      <div className='flex flex-col px-4 py-2 gap-2'>
        <div className='text-gray-900 font-medium text-[13px]'>Automatic Recharge</div>
        <div className='flex flex-row gap-4 items-center'>
          <Switch checked={isOn} onCheckedChange={setIsOn} />
          <div className='text-gray-700 font-normal text-[13px]'>
            Yes, automatically recharge my card when my credit balance falls below a threshold
          </div>
        </div>
      </div>

      {isOn && (
        <div className='flex flex-col px-4 py-2 gap-2'>
          <div className='flex flex-col gap-1'>
            <div className='text-gray-900 font-medium text-[13px]'>When credit balance goes below</div>
            <CurrencyInput amount={automaticPaymentThreshold} setAmount={setAutomaticPaymentThreshold} />
            <div className='text-gray-500 font-normal text-[12px]'>Enter an amount between $5 and $5000</div>
          </div>

          <div className='flex flex-col gap-1'>
            <div className='text-gray-900 font-medium text-[13px]'>Bring credit balance up to</div>
            <CurrencyInput amount={balanceToMaintain} setAmount={setBalanceToMaintain} />
            <div className='text-gray-500 font-normal text-[12px]'>Enter an amount between $5.01 and $5000</div>
          </div>
        </div>
      )}

      <BottomButtonBar
        actionText='Save'
        onCancel={() => setIsOpen(false)}
        onAction={() => onSaveSettings()}
        isActionDisabled={!isSaveActive}
      />
    </div>
  );
}
