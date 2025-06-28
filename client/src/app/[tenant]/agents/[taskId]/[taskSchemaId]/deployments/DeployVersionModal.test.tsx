import { VersionV1 } from '@/types/workflowAI';

// Test the filtering logic directly
describe('DeployVersionModal filtering logic', () => {
  const mockVersions = [
    { id: 'v1', iteration: 1, schema_id: 1, is_favorite: false },
    { id: 'v2', iteration: 2, schema_id: 1, is_favorite: true }, // Currently deployed
    { id: 'v3', iteration: 3, schema_id: 1, is_favorite: false },
    { id: 'v4', iteration: 4, schema_id: 1, is_favorite: true },
    { id: 'v5', iteration: 5, schema_id: 2, is_favorite: false }, // Different schema
  ];

  const currentSchemaId = '1';
  const currentIteration = '2'; // Version 2 is currently deployed

  it('should filter versions by schema ID and exclude currently deployed version', () => {
    // Simulate the filtering logic from the component
    const filteredVersions = mockVersions.filter((version) => {
      // Filter by schema ID
      if (`${version.schema_id}` !== currentSchemaId) return false;

      // Filter out already deployed version for this environment
      if (currentIteration && version.iteration.toString() === currentIteration) {
        return false;
      }

      return true;
    });

    expect(filteredVersions).toHaveLength(3);
    expect(filteredVersions.map((v) => v.iteration)).toEqual([1, 3, 4]);
    expect(filteredVersions.find((v) => v.iteration === 2)).toBeUndefined(); // Currently deployed version should be excluded
    expect(filteredVersions.find((v) => v.iteration === 5)).toBeUndefined(); // Different schema should be excluded
  });

  it('should filter favorites by schema ID and exclude currently deployed version', () => {
    const favoriteVersions = mockVersions.filter((v) => v.is_favorite);

    const filteredFavorites = favoriteVersions.filter((version) => {
      // Filter by schema ID
      if (`${version.schema_id}` !== currentSchemaId) return false;

      // Filter out already deployed version for this environment
      if (currentIteration && version.iteration.toString() === currentIteration) {
        return false;
      }

      return true;
    });

    expect(filteredFavorites).toHaveLength(1);
    expect(filteredFavorites[0].iteration).toBe(4);
    expect(filteredFavorites.find((v) => v.iteration === 2)).toBeUndefined(); // Currently deployed favorite should be excluded
  });

  it('should show all versions when no current iteration is set', () => {
    const filteredVersions = mockVersions.filter((version) => {
      // Filter by schema ID
      if (`${version.schema_id}` !== currentSchemaId) return false;

      // No current iteration to filter out
      return true;
    });

    expect(filteredVersions).toHaveLength(4); // All versions from schema 1
    expect(filteredVersions.map((v) => v.iteration)).toEqual([1, 2, 3, 4]);
  });

  it('should filter by different schema ID correctly', () => {
    const differentSchemaId = '2';

    const filteredVersions = mockVersions.filter((version) => {
      // Filter by schema ID
      if (`${version.schema_id}` !== differentSchemaId) return false;

      // Filter out already deployed version for this environment
      if (currentIteration && version.iteration.toString() === currentIteration) {
        return false;
      }

      return true;
    });

    expect(filteredVersions).toHaveLength(1);
    expect(filteredVersions[0].iteration).toBe(5);
  });
});
