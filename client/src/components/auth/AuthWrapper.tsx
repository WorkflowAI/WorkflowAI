// eslint-disable-next-line no-restricted-imports
import { ClerkProvider } from '@clerk/nextjs';
import { ReactNode } from 'react';
import { DISABLE_AUTHENTICATION } from '@/lib/constants';
import { ClerkLoader } from './ClerkLoader';
import { NoAuthProvider } from './NoAuthProvider';

export async function AuthWrapper({ children }: { children: ReactNode }) {
  if (DISABLE_AUTHENTICATION) {
    return <NoAuthProvider>{children}</NoAuthProvider>;
  }
  return (
    <ClerkProvider allowedRedirectOrigins={['https://anotherai.dev']}>
      <ClerkLoader>{children}</ClerkLoader>
    </ClerkProvider>
  );
}
