import { generateMetadataWithTitle } from '@/lib/metadata';
import { TaskSchemaParams } from '@/lib/routeFormatter';
import { Playground } from './playground/playground';

export async function generateMetadata({ params }: { params: TaskSchemaParams }) {
  return generateMetadataWithTitle('Playground', params);
}

type PlaygroundPageProps = {
  params: TaskSchemaParams;
};

export default function PlaygroundPage(props: PlaygroundPageProps) {
  return <Playground {...props.params} />;
}
