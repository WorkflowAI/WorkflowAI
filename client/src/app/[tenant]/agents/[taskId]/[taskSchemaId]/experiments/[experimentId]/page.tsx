import { generateMetadataWithTitle } from '@/lib/metadata';
import { TaskSchemaParams } from '@/lib/routeFormatter';
import { ExperimentContainer } from './ExperimentContainer';

export async function generateMetadata({ params }: { params: TaskSchemaParams }) {
  return generateMetadataWithTitle('Experiment', params);
}

export default function ExperimentsPage() {
  return <ExperimentContainer />;
}
