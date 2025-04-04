import { cleanURL, looksLikeURL } from '@/app/landing/sections/SuggestedFeatures/utils';
import { generateMetadataWithTitleForTenant } from '@/lib/metadata';
import { TenantID } from '@/types/aliases';
import { URLLandingPage } from '../landing/URLLandingPage';
import { TasksContainer } from './agents/tasks/TasksContainer';

export async function generateMetadata({ params }: { params: { tenant: string } }) {
  // Handle the tenant parameter which may contain the full URL path
  const decodedTenant = decodeURIComponent(params.tenant) as TenantID;
  return generateMetadataWithTitleForTenant('AI Agents', decodedTenant);
}

export default function TasksPage({ params: { tenant } }: { params: { tenant: string } }) {
  // Handle the tenant parameter which may contain the full URL path
  const decodedTenant = decodeURIComponent(tenant) as TenantID;

  // Split the tenant into parts and check if the first part is a URL
  const parts = decodedTenant.split('/');
  const firstPart = parts[0];

  if (looksLikeURL(firstPart)) {
    const companyURL = cleanURL(firstPart);
    return <URLLandingPage companyURL={companyURL} />;
  }

  // Otherwise, use the tenant as is
  return <TasksContainer tenant={decodedTenant} />;
}
