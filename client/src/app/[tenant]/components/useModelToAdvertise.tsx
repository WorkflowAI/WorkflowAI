import { useCallback, useMemo } from 'react';
import { useLocalStorage } from 'usehooks-ts';

type ModelToAdvertise = {
  name: string;
  date: string;
  modelId: string;
};

const MODELS_TO_ADVERTISE: ModelToAdvertise[] = [
  {
    name: 'Claude 4 Sonnet',
    date: '2025-05-22',
    modelId: 'claude-sonnet-4-20250514',
  },
  {
    name: 'Claude 4 Opus',
    date: '2025-05-22',
    modelId: 'claude-opus-4-20250514',
  },
];

const STORAGE_KEY = 'dismissedModels';

export function useModelToAdvertise() {
  const [dismissedModels, setDismissedModels] = useLocalStorage<string[]>(STORAGE_KEY, []);

  const modelsToAdvertise = useMemo(() => {
    const result = MODELS_TO_ADVERTISE.filter((model) => {
      if (dismissedModels.includes(model.name)) {
        return false;
      }

      const date = new Date(model.date);
      const now = new Date();
      const diffTime = Math.abs(now.getTime() - date.getTime());
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      return diffDays <= 3;
    });

    if (result.length === 0) {
      return undefined;
    }

    return result.map((model) => [model.name, model.modelId]) as [string, string][];
  }, [dismissedModels]);

  const dismiss = useCallback(
    (models: [string, string][]) => {
      setDismissedModels((prev) => [...prev, ...models.map((model) => model[1])]);
    },
    [setDismissedModels]
  );

  return {
    modelsToAdvertise,
    dismiss,
  };
}
