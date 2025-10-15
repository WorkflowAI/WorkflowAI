import { generateMetadataWithTitle } from '@/lib/metadata';
import { TaskSchemaParams } from '@/lib/routeFormatter';
import { ApiContainerWrapper } from './ApiContainerWrapper';

export async function generateMetadata({ params }: { params: TaskSchemaParams }) {
  return generateMetadataWithTitle('Migration', params);
}

export default function MigrationPage() {
  return <ApiContainerWrapper />;
}
