import { useEffect, useMemo, useState } from 'react';
import { TaskSchemaID } from '@/types/aliases';
import { GeneralizedTaskInput } from '@/types/task_run';
import { MajorVersion } from '@/types/workflowAI';

export function usePlaygroundFirstGenerationFlow(
  schemaId: TaskSchemaID,
  majorVersion: MajorVersion | undefined,
  instructions: string,
  input: GeneralizedTaskInput | undefined,
  generateInput: () => Promise<void>,
  generateInstructions: () => Promise<void>
) {
  // Generating first instructions
  const [startedGeneratingInstructions, setStartedGeneratingInstructions] = useState(false);

  const shouldGenerateInstructions = useMemo(() => {
    if (!!majorVersion || (!!instructions && instructions !== '') || startedGeneratingInstructions) {
      return false;
    }
    return true;
  }, [majorVersion, instructions, startedGeneratingInstructions]);

  useEffect(() => {
    if (shouldGenerateInstructions && !startedGeneratingInstructions) {
      setStartedGeneratingInstructions(true);
      generateInstructions();
    }
  }, [shouldGenerateInstructions, generateInstructions, startedGeneratingInstructions]);

  // Generating first input
  const [startedGeneratingInput, setStartedGeneratingInput] = useState(false);

  const shouldGenerateInput = useMemo(() => {
    if (!instructions || instructions === '' || input !== undefined || startedGeneratingInput) {
      return false;
    }
    return true;
  }, [instructions, input, startedGeneratingInput]);

  useEffect(() => {
    if (shouldGenerateInput && !startedGeneratingInput) {
      setStartedGeneratingInput(true);
      generateInput();
    }
  }, [shouldGenerateInput, generateInput, startedGeneratingInput]);

  return;
}
