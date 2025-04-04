import { generateMetadataWithTitle } from '@/lib/metadata';
import { TaskSchemaParams } from '@/lib/routeFormatter';
import { DeploymentsContainer } from './DeploymentsContainer';

export async function generateMetadata({ params }: { params: TaskSchemaParams }) {
  return generateMetadataWithTitle('Deployments', params);
}

export default function DeploymentsPage() {
  return <DeploymentsContainer />;
}
