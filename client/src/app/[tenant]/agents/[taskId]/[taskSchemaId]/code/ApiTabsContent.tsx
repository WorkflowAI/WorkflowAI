import { Loader } from '@/components/ui/Loader';
import { TaskSchemaParams } from '@/lib/routeFormatter';
import { TaskRun, TaskSchemaResponseWithSchema } from '@/types';
import { CodeLanguage } from '@/types/snippets';
import { VersionEnvironment, VersionV1 } from '@/types/workflowAI';
import { GoApiTab } from './GoApiTab';
import { PythonApiTab } from './PythonApiTab';
import { RestApiTab } from './RestApiTab';
import { TypeScriptApiTab } from './TypeScriptApiTab';

type ApiTabsContentProps = TaskSchemaParams & {
  taskSchema: TaskSchemaResponseWithSchema | undefined;
  taskRun: TaskRun | undefined;
  version: VersionV1 | undefined;
  environment: VersionEnvironment | undefined;
  language: string | undefined;
  apiUrl: string | undefined;
  secondaryInput: Record<string, unknown> | undefined;
};

export function ApiTabsContent(props: ApiTabsContentProps) {
  const { tenant, taskId, taskSchemaId, taskSchema, taskRun, version, environment, language, apiUrl, secondaryInput } =
    props;

  if (!taskSchema || !version || !language) {
    return <Loader centered />;
  }

  switch (language) {
    case CodeLanguage.TYPESCRIPT:
      return (
        <TypeScriptApiTab
          taskSchema={taskSchema}
          taskRun={taskRun}
          version={version}
          environment={environment}
          apiUrl={apiUrl}
          secondaryInput={secondaryInput}
        />
      );
    case CodeLanguage.PYTHON:
      return (
        <PythonApiTab
          tenant={tenant}
          taskId={taskId}
          taskSchemaId={taskSchemaId}
          environment={environment}
          iteration={environment ? undefined : version.iteration}
          taskRun={taskRun}
          apiUrl={apiUrl}
          secondaryInput={secondaryInput}
          semver={version.semver}
        />
      );
    case CodeLanguage.REST:
      return (
        <RestApiTab
          tenant={tenant}
          taskId={taskId}
          taskSchemaId={taskSchemaId}
          environment={environment}
          taskRun={taskRun}
          version={version}
          apiUrl={apiUrl}
        />
      );
    case CodeLanguage.GO:
      return (
        <GoApiTab
          tenant={tenant}
          taskId={taskId}
          taskSchemaId={taskSchemaId}
          environment={environment}
          taskRun={taskRun}
          version={version}
          apiUrl={apiUrl}
        />
      );
    case CodeLanguage.BASH:
      return null;
  }
}
