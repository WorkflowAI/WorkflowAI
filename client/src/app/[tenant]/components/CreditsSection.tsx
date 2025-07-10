import { Warning12Filled } from '@fluentui/react-icons';
import { useCallback } from 'react';
import { CircularProgress } from '@/components/ui/CircularProgress';
import { formatCurrency } from '@/lib/formatters/numberFormatters';
import { signUpRoute } from '@/lib/routeFormatter';
import { useOrFetchOrganizationSettings } from '@/store';
import { ManageCards } from './ManageCards/ManageCards';

type CreditsSectionProps = {
  isSignedIn: boolean;
};

export function CreditsSection(props: CreditsSectionProps) {
  const { isSignedIn } = props;
  const { organizationSettings, fetchSettings } = useOrFetchOrganizationSettings(30000);

  const onHovering = useCallback(() => {
    fetchSettings();
  }, [fetchSettings]);

  const addedCredits = organizationSettings?.added_credits_usd;
  const currentCredits = organizationSettings?.current_credits_usd;

  const lowCreditsMode = !!currentCredits && currentCredits <= 5;

  const progress = addedCredits === 0 || !currentCredits || !addedCredits ? 0 : (currentCredits / addedCredits) * 100;

  const content = (
    <div
      className='flex flex-row gap-1.5 px-2.5 w-full justify-between items-center min-h-12 bg-gray-50 rounded-b-sm shadow-[inset_0_2px_4px_rgba(0,0,0,0.05)] cursor-pointer'
      onMouseEnter={onHovering}
    >
      <div className='flex flex-col'>
        <div className='text-xs font-medium text-gray-800'>{formatCurrency(currentCredits)}</div>
        <div className='text-xs font-normal text-gray-500'>Credits Left</div>
      </div>
      <div className='relative flex w-6 h-6 items-center'>
        <CircularProgress value={progress} warning={lowCreditsMode} />
        {lowCreditsMode ? (
          <div className='absolute inset-0 flex items-center justify-center text-red-500'>
            <Warning12Filled />
          </div>
        ) : (
          <div className='absolute inset-0 bg-gradient-to-t from-transparent to-white opacity-70 z-10' />
        )}
      </div>
    </div>
  );

  const routeForSignUp = signUpRoute();

  if (!isSignedIn) {
    return (
      <a href={routeForSignUp} className='w-full h-full'>
        {content}
      </a>
    );
  }

  return <ManageCards organizationSettings={organizationSettings}>{content}</ManageCards>;
}
