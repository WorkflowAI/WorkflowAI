import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { VersionV1 } from '@/types/workflowAI';
import { DeployVersionModal, EditEnvSchemaIterationParams } from './DeployVersionModal';

// Mock the TaskVersionsListSection component since we're testing filtering logic
jest.mock('@/components/v2/TaskVersions/TaskVersionsListSection', () => {
  return {
    TaskVersionsListSection: ({ versionsToShow, title }: { versionsToShow: VersionV1[]; title?: string }) => (
      <div
        data-testid={
          title ? `versions-section-${title.toLowerCase().replace(/\s+/g, '-')}` : 'versions-section-favorites'
        }
      >
        {versionsToShow.map((version) => (
          <div key={version.id} data-testid={`version-${version.iteration}`}>
            Version {version.iteration}
          </div>
        ))}
      </div>
    ),
  };
});

// Mock other dependencies
jest.mock('@/app/[tenant]/components/TaskSwitcherContainer', () => ({
  SchemaSelectorContainer: () => <div data-testid='schema-selector' />,
}));

jest.mock('@/components/ui/Button', () => ({
  Button: ({ children, ...props }: any) => <button {...props}>{children}</button>,
}));

jest.mock('@/components/ui/Dialog', () => ({
  Dialog: ({ children, open }: any) => (open ? <div data-testid='dialog'>{children}</div> : null),
  DialogContent: ({ children }: any) => <div data-testid='dialog-content'>{children}</div>,
  DialogHeader: ({ children, title }: any) => (
    <div data-testid='dialog-header'>
      <h2>{title}</h2>
      {children}
    </div>
  ),
}));

jest.mock('@/components/ui/Loader', () => ({
  Loader: () => <div data-testid='loader'>Loading...</div>,
}));

// Create mock versions for testing
const createMockVersion = (id: string, iteration: number, schemaId: number, isFavorite = false): VersionV1 => {
  return {
    id,
    iteration,
    schema_id: schemaId,
    is_favorite: isFavorite,
    created_at: '2024-01-01T00:00:00Z',
    last_active_at: '2024-01-01T00:00:00Z',
    model: 'gpt-4',
    properties: {},
    cost_estimate_usd: 0.01,
    created_by: null,
    favorited_by: null,
    deployments: [],
    notes: null,
    run_count: 0,
    semver: '1.0.0',
  } as VersionV1;
};

describe('DeployVersionModal', () => {
  const defaultProps = {
    isInitialized: true,
    onClose: jest.fn(),
    onDeploy: jest.fn(),
    onIterationChange: jest.fn(),
    taskId: 'test-task' as any,
    tenant: 'test-tenant' as any,
  };

  const mockVersions = [
    createMockVersion('v1', 1, 1, false),
    createMockVersion('v2', 2, 1, true), // This will be the currently deployed version
    createMockVersion('v3', 3, 1, false),
    createMockVersion('v4', 4, 1, true),
    createMockVersion('v5', 5, 2, false), // Different schema
  ];

  const mockFavoriteVersions = mockVersions.filter((v) => v.is_favorite);

  const mockEnvSchemaIteration: EditEnvSchemaIterationParams = {
    environment: 'production',
    schemaId: '1' as any,
    currentIteration: '2', // Version 2 is currently deployed
    iteration: null,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should not render when envSchemaIteration is undefined', () => {
    render(
      <DeployVersionModal
        {...defaultProps}
        allVersions={mockVersions}
        favoriteVersions={mockFavoriteVersions}
        envSchemaIteration={undefined}
        setEnvSchemaIteration={jest.fn()}
      />
    );

    expect(screen.queryByTestId('dialog')).not.toBeInTheDocument();
  });

  it('should render dialog when envSchemaIteration is provided', () => {
    render(
      <DeployVersionModal
        {...defaultProps}
        allVersions={mockVersions}
        favoriteVersions={mockFavoriteVersions}
        envSchemaIteration={mockEnvSchemaIteration}
        setEnvSchemaIteration={jest.fn()}
      />
    );

    expect(screen.getByTestId('dialog')).toBeInTheDocument();
    expect(screen.getByText(/Update production Version for Schema #1/)).toBeInTheDocument();
  });

  it('should filter out currently deployed version from favorites', () => {
    render(
      <DeployVersionModal
        {...defaultProps}
        allVersions={mockVersions}
        favoriteVersions={mockFavoriteVersions}
        envSchemaIteration={mockEnvSchemaIteration}
        setEnvSchemaIteration={jest.fn()}
      />
    );

    const favoritesSection = screen.getByTestId('versions-section-favorites');

    // Should show version 4 (favorite, schema 1, not currently deployed)
    expect(screen.getByTestId('version-4')).toBeInTheDocument();

    // Should NOT show version 2 (currently deployed to production)
    expect(screen.queryByTestId('version-2')).not.toBeInTheDocument();
  });

  it('should filter out currently deployed version from all versions', () => {
    render(
      <DeployVersionModal
        {...defaultProps}
        allVersions={mockVersions}
        favoriteVersions={mockFavoriteVersions}
        envSchemaIteration={mockEnvSchemaIteration}
        setEnvSchemaIteration={jest.fn()}
      />
    );

    const allVersionsSection = screen.getByTestId('versions-section-all-versions');

    // Should show versions 1, 3, 4 (all from schema 1, excluding currently deployed version 2)
    expect(screen.getByTestId('version-1')).toBeInTheDocument();
    expect(screen.getByTestId('version-3')).toBeInTheDocument();
    expect(screen.getByTestId('version-4')).toBeInTheDocument();

    // Should NOT show version 2 (currently deployed)
    expect(screen.queryByTestId('version-2')).not.toBeInTheDocument();

    // Should NOT show version 5 (different schema)
    expect(screen.queryByTestId('version-5')).not.toBeInTheDocument();
  });

  it('should show all versions when no current iteration is set', () => {
    const envSchemaIterationWithoutCurrent = {
      ...mockEnvSchemaIteration,
      currentIteration: null,
    };

    render(
      <DeployVersionModal
        {...defaultProps}
        allVersions={mockVersions}
        favoriteVersions={mockFavoriteVersions}
        envSchemaIteration={envSchemaIterationWithoutCurrent}
        setEnvSchemaIteration={jest.fn()}
      />
    );

    // Should show all versions from schema 1 since there's no currently deployed version to filter out
    expect(screen.getByTestId('version-1')).toBeInTheDocument();
    expect(screen.getByTestId('version-2')).toBeInTheDocument();
    expect(screen.getByTestId('version-3')).toBeInTheDocument();
    expect(screen.getByTestId('version-4')).toBeInTheDocument();

    // Should NOT show version 5 (different schema)
    expect(screen.queryByTestId('version-5')).not.toBeInTheDocument();
  });

  it('should filter by schema ID correctly', () => {
    const envSchemaIterationSchema2 = {
      ...mockEnvSchemaIteration,
      schemaId: '2' as any,
      currentIteration: null,
    };

    render(
      <DeployVersionModal
        {...defaultProps}
        allVersions={mockVersions}
        favoriteVersions={mockFavoriteVersions}
        envSchemaIteration={envSchemaIterationSchema2}
        setEnvSchemaIteration={jest.fn()}
      />
    );

    // Should only show version 5 (schema 2)
    expect(screen.getByTestId('version-5')).toBeInTheDocument();

    // Should NOT show versions 1-4 (schema 1)
    expect(screen.queryByTestId('version-1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('version-2')).not.toBeInTheDocument();
    expect(screen.queryByTestId('version-3')).not.toBeInTheDocument();
    expect(screen.queryByTestId('version-4')).not.toBeInTheDocument();
  });

  it('should disable deploy button when selected iteration equals current iteration', () => {
    const envSchemaIterationWithSelection = {
      ...mockEnvSchemaIteration,
      iteration: '2', // Same as currentIteration
    };

    render(
      <DeployVersionModal
        {...defaultProps}
        allVersions={mockVersions}
        favoriteVersions={mockFavoriteVersions}
        envSchemaIteration={envSchemaIterationWithSelection}
        setEnvSchemaIteration={jest.fn()}
      />
    );

    const deployButton = screen.getByRole('button', { name: 'Deploy' });
    expect(deployButton).toBeDisabled();
  });

  it('should enable deploy button when selected iteration differs from current iteration', () => {
    const envSchemaIterationWithSelection = {
      ...mockEnvSchemaIteration,
      iteration: '3', // Different from currentIteration (2)
    };

    render(
      <DeployVersionModal
        {...defaultProps}
        allVersions={mockVersions}
        favoriteVersions={mockFavoriteVersions}
        envSchemaIteration={envSchemaIterationWithSelection}
        setEnvSchemaIteration={jest.fn()}
      />
    );

    const deployButton = screen.getByRole('button', { name: 'Deploy' });
    expect(deployButton).not.toBeDisabled();
  });
});
