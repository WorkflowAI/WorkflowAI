import { useMemo } from 'react';
import { MajorVersion } from '@/types/workflowAI';

type Props = {
  majorVersions: MajorVersion[];
  temperature: number | undefined;
  instructions: string | undefined;
  variantId: string | undefined;
  userSelectedMajor: number | undefined;
};

export function useMatchVersion(props: Props) {
  const { majorVersions, temperature, instructions, variantId, userSelectedMajor } = props;

  const matchedVersion = useMemo(() => {
    const matchingVersions = majorVersions.filter((version) => {
      const normalizedVersionInstructions = version.properties.instructions?.toLowerCase().trim() || '';

      const normalizedInstructions = instructions?.toLowerCase().trim() || '';

      return (
        version.properties.temperature === temperature &&
        normalizedVersionInstructions === normalizedInstructions &&
        version.properties.task_variant_id === variantId
      );
    });

    const allMatchedVersions = matchingVersions.sort((a, b) => b.major - a.major);

    if (userSelectedMajor !== undefined) {
      const result = allMatchedVersions.find((version) => version.major === userSelectedMajor);

      if (result !== undefined) {
        return result;
      }

      return allMatchedVersions[0];
    }

    return allMatchedVersions[0];
  }, [majorVersions, temperature, instructions, userSelectedMajor, variantId]);

  return { matchedVersion };
}
