import { generateMetadataWithTitle } from '@/lib/metadata';
import { TaskSchemaParams } from '@/lib/routeFormatter';
import { ExperimentsContainer } from './ExperimentsContainer';

export async function generateMetadata({ params }: { params: TaskSchemaParams }) {
  return generateMetadataWithTitle('Experiments', params);
}

export default function ExperimentsPage() {
  return <ExperimentsContainer />;
}
