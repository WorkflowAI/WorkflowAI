'use client';

import { useMemo } from 'react';
import { Loader } from '@/components/ui/Loader';
import { CodeBlock } from '@/components/v2/CodeBlock';
import { useOrFetchTaskSnippet } from '@/store';
import { TaskRun } from '@/types';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { CodeLanguage, InstallInstruction } from '@/types/snippets';
import { VersionEnvironment, VersionV1 } from '@/types/workflowAI';
import { versionForCodeGeneration } from './utils';

type GoApiTabProps = {
  tenant: TenantID;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  taskRun: TaskRun | undefined;
  environment?: VersionEnvironment;
  version: VersionV1;
  apiUrl: string | undefined;
  secondaryInput?: Record<string, unknown>;
};

export function GoApiTab(props: GoApiTabProps) {
  const { tenant, taskId, taskSchemaId, environment, taskRun: rawTaskRun, version, apiUrl, secondaryInput } = props;

  const taskRunJSON = useMemo(() => JSON.stringify({ task_output: rawTaskRun?.task_output }, null, 2), [rawTaskRun]);
  
  const v = useMemo(() => {
    if (!rawTaskRun) return undefined;
    const versionValue = versionForCodeGeneration(environment, version);
    // Convert to string if it's a number
    return typeof versionValue === 'number' ? String(versionValue) : versionValue;
  }, [environment, version, rawTaskRun]);

  const { taskSnippet, isInitialized: isSnippetInitialized } = useOrFetchTaskSnippet(
    tenant,
    taskId,
    taskSchemaId,
    CodeLanguage.GO,
    rawTaskRun?.task_input,
    undefined,
    v,
    apiUrl,
    secondaryInput
  );

  const installCode = useMemo(() => {
    if (taskSnippet && InstallInstruction.SDK in taskSnippet) {
      return taskSnippet[InstallInstruction.SDK].code;
    }
    return 'go get github.com/workflowai/workflowai-go';
  }, [taskSnippet]);

  const code = useMemo(() => {
    if (!taskSnippet) {
      return '';
    }
    
    if (InstallInstruction.RUN in taskSnippet) {
      const runSnippet = taskSnippet[InstallInstruction.RUN];
      
      // Check if the run snippet is a simple Snippet with code property
      if ('code' in runSnippet) {
        return runSnippet.code.replace('__WORKFLOWAI_API_TOKEN__', 'Add your API key here');
      }
      
      // If it's a RunSnippet (with run.code property), handle differently
      if ('run' in runSnippet && 'code' in runSnippet.run) {
        // For Go, we don't expect to get here, but handling it just in case
        return runSnippet.run.code.replace('__WORKFLOWAI_API_TOKEN__', 'Add your API key here');
      }
    }
    
    return '';
  }, [taskSnippet]);

  if (!isSnippetInitialized) {
    return <Loader centered />;
  }

  if (!taskSnippet) {
    return <div className='flex-1 flex items-center justify-center'>Failed to load task snippet</div>;
  }

  return (
    <div className='flex flex-col w-full h-full overflow-y-auto'>
      <CodeBlock language='Bash' snippet={installCode} />
      <CodeBlock language='Go' snippet={code} showTopBorder={true} />
      <CodeBlock language='JSON' snippet={taskRunJSON} showCopyButton={false} showTopBorder={true} />
    </div>
  );
} 