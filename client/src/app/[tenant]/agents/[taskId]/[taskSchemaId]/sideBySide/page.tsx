import { generateMetadataWithTitle } from '@/lib/metadata';
import { TaskSchemaParams } from '@/lib/routeFormatter';
import { SideBySideContainer } from './SideBySideContainer';

export async function generateMetadata({ params }: { params: TaskSchemaParams }) {
  return generateMetadataWithTitle('Side by Side', params);
}

export default function SideBySidePage() {
  return <SideBySideContainer />;
}
