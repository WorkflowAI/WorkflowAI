import { headers } from 'next/headers';
import { BACKEND_API_URL } from '@/lib/constants';
import { TaskSchemaParams } from '@/lib/routeFormatter';
import { getTaskDescription } from '@/lib/taskMetadata';
import { SerializableTask } from '@/types/workflowAI';

export async function generateMetadata({ params }: { params: TaskSchemaParams }) {
  const { tenant, taskId } = params;
  const headersList = headers();
  const requestUrl = headersList.get('x-request-url');
  const baseUrl = requestUrl ? new URL(requestUrl).origin : '';

  try {
    const task: SerializableTask = await fetch(`${BACKEND_API_URL}/${tenant}/agents/${taskId}`).then((res) =>
      res.json()
    );

    const description = getTaskDescription(task);

    const previewImageUrl = `${baseUrl}/api/agents/images/${tenant}/${taskId}`;

    return {
      openGraph: {
        description,
        images: [previewImageUrl],
      },
      twitter: {
        card: 'summary_large_image',
        title: task.name,
        description,
        images: [previewImageUrl],
      },
    };
  } catch (error) {
    console.error(error);
    return {
      openGraph: {},
    };
  }
}
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <div className='flex-1 overflow-y-auto w-full h-full'>{children}</div>;
}
