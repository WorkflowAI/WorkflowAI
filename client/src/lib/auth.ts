// eslint-disable-next-line no-restricted-imports
import { auth as clerkAuth, currentUser as clerkCurrentUser } from '@clerk/nextjs/server';
import { User, clerkUserToUser } from '@/types/user';
import { getTenantSlug } from './auth_utils';
import { DISABLE_AUTHENTICATION, HARDCODED_TENANT } from './constants';

interface AuthResult {
  orgSlug?: string | null;
  orgId?: string | null;
  redirectToSignIn: (options: { returnBackUrl: string }) => null;
}

export function auth(): AuthResult {
  if (DISABLE_AUTHENTICATION) {
    return {
      orgSlug: HARDCODED_TENANT,
      orgId: HARDCODED_TENANT,
      redirectToSignIn: () => null,
    };
  }
  return clerkAuth();
}

export async function currentUser(): Promise<User | null> {
  if (DISABLE_AUTHENTICATION) {
    return { id: '1' };
  }
  const clerkUser = await clerkCurrentUser();
  if (!clerkUser) {
    return null;
  }
  return clerkUserToUser(clerkUser);
}

export async function tenantSlug(): Promise<string | undefined> {
  const user = await currentUser();
  if (!user) {
    return undefined;
  }
  const authResult = auth();
  if (!authResult) {
    return undefined;
  }
  return getTenantSlug({ slug: authResult.orgSlug }, user);
}
