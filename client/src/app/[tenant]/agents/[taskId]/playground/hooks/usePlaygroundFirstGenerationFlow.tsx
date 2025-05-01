import { useEffect, useMemo, useRef } from 'react';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { GeneralizedTaskInput } from '@/types/task_run';
import { MajorVersion } from '@/types/workflowAI';

export function usePlaygroundFirstGenerationFlow(
  tenant: TenantID | undefined,
  taskId: TaskID,
  schemaId: TaskSchemaID,
  majorVersion: MajorVersion | undefined,
  instructions: string,
  input: GeneralizedTaskInput | undefined,
  generateInput: () => Promise<void>,
  generateInstructions: () => Promise<void>
) {
  // Generating first instructions
  const startedGeneratingInstructions = useRef(false);

  const shouldGenerateInstructions = useMemo(() => {
    if (!!majorVersion || (!!instructions && instructions !== '') || startedGeneratingInstructions.current) {
      return false;
    }
    return true;
  }, [majorVersion, instructions]);

  useEffect(() => {
    if (shouldGenerateInstructions && !startedGeneratingInstructions.current) {
      startedGeneratingInstructions.current = true;
      generateInstructions();
    }
  }, [shouldGenerateInstructions, generateInstructions]);

  // Generating first input
  const startedGeneratingInput = useRef(false);

  const shouldGenerateInput = useMemo(() => {
    if (!instructions || instructions === '' || input !== undefined || startedGeneratingInput.current) {
      return false;
    }
    return true;
  }, [instructions, input]);

  useEffect(() => {
    if (shouldGenerateInput && !startedGeneratingInput.current) {
      startedGeneratingInput.current = true;
      generateInput();
    }
  }, [shouldGenerateInput, generateInput]);

  return;
}
