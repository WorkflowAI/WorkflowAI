import { GeneralizedTaskInput, isNullish } from '@/types';
import { Model } from '@/types/aliases';
import { RunTaskOptions } from './usePlaygroundPersistedState';

export function formatTaskRunIdParam(index: number) {
  return `taskRunId${index + 1}`;
}

export type PlaygroundModels = [Model | null | undefined, Model | null | undefined, Model | null | undefined];

/**
 * Calculates the difference between two texts by finding where the new text
 * overlaps with the old text. This is useful for handling streaming responses
 * where new chunks of text need to be merged with existing text.
 *
 * The algorithm:
 * 1. Handles empty string cases first
 * 2. For each position in the new text, takes the remaining substring
 * 3. Looks for that substring in the old text
 * 4. When found, combines:
 *    - the complete new text
 *    - any remaining text from the old string after the overlap
 * 5. If no overlap is found, simply concatenates the strings
 *
 * @param oldText - The existing text
 * @param newText - The new text to merge
 * @returns The merged text preserving as much of both strings as possible
 */
export function calculateTextDiff(oldText: string | undefined, newText: string | undefined): string {
  if (!newText?.length) {
    return oldText ?? '';
  }

  if (!oldText?.length) {
    return newText ?? '';
  }

  for (let i = 0; i < newText.length; i++) {
    const endPart = newText.slice(i);
    const index = oldText.indexOf(endPart);
    if (index !== -1) {
      return newText + oldText.slice(index + endPart.length);
    }
  }

  return newText + oldText.slice(newText.length);
}

type RunState = {
  generatedInput: GeneralizedTaskInput | undefined;
  instructions: string | undefined;
  temperature: number | undefined;
  variantId: string | undefined;
};

function pickFinalGeneratedInput(
  options: Pick<RunTaskOptions, 'externalGeneratedInput'>,
  state: Pick<RunState, 'generatedInput'>
) {
  return options.externalGeneratedInput ?? state.generatedInput;
}

function pickFinalInstructions(
  options: Pick<RunTaskOptions, 'externalInstructions' | 'externalVersion'>,
  state: Pick<RunState, 'instructions'>
) {
  if (!isNullish(options.externalInstructions)) {
    return options.externalInstructions;
  }
  if (!isNullish(options.externalVersion)) {
    return options.externalVersion.properties.instructions;
  }

  return state.instructions;
}

function pickFinalTemperature(
  options: Pick<RunTaskOptions, 'externalTemperature' | 'externalVersion'>,
  state: Pick<RunState, 'temperature'>
) {
  if (!isNullish(options.externalTemperature)) {
    return options.externalTemperature;
  }
  if (!isNullish(options.externalVersion)) {
    return options.externalVersion.properties.temperature;
  }
  return state.temperature;
}

function pickFinalVariantId(options: Pick<RunTaskOptions, 'externalVersion'>, state: Pick<RunState, 'variantId'>) {
  if (!isNullish(options.externalVersion)) {
    return options.externalVersion.properties.task_variant_id;
  }
  return state.variantId;
}

export function pickFinalRunProperties(options: RunTaskOptions, state: RunState) {
  return {
    finalGeneratedInput: pickFinalGeneratedInput(options, state),
    finalInstructions: pickFinalInstructions(options, state),
    finalTemperature: pickFinalTemperature(options, state),
    finalVariantId: pickFinalVariantId(options, state),
  };
}
