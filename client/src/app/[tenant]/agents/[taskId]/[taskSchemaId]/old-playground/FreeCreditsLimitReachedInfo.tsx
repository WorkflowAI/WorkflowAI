import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { signUpRoute } from '@/lib/routeFormatter';

export function FreeCreditsLimitReachedInfo() {
  const routeForSignUp = signUpRoute();

  return (
    <div className='flex flex-col items-center'>
      <AlertTriangle size={24} className='text-gray-400 mb-4' />
      <div className='text-gray-700 font-semibold text-[13px] mb-1'>Free Credit Limit Reached</div>
      <div className='text-gray-500 font-normal text-[13px] mb-6'>
        Create an account to continue using this AI agent.
      </div>
      <Button variant='newDesign' size='sm' toRoute={routeForSignUp}>
        Create Account
      </Button>
    </div>
  );
}
