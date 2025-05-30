import { generateMetadataWithTitle } from '@/lib/metadata';
import { TaskSchemaParams } from '@/lib/routeFormatter';
import { PlaygroundContentWrapper } from './playground/playgroundContentWrapper';

export async function generateMetadata({ params }: { params: TaskSchemaParams }) {
  return generateMetadataWithTitle('Playground', params);
}

type Props = {
  params: TaskSchemaParams;
};

export default function PlaygroundPage(props: Props) {
  const { tenant, taskId, taskSchemaId } = props.params;

  return <PlaygroundContentWrapper tenant={tenant} taskId={taskId} taskSchemaId={taskSchemaId} />;
}
