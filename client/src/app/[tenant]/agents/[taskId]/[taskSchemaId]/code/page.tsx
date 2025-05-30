import { generateMetadataWithTitle } from '@/lib/metadata';
import { TaskSchemaParams } from '@/lib/routeFormatter';
import { ApiContainerWrapper } from './ApiContainerWrapper';

export async function generateMetadata({ params }: { params: TaskSchemaParams }) {
  return generateMetadataWithTitle('Code', params);
}

export default function BenchmarksPage() {
  return <ApiContainerWrapper />;
}
