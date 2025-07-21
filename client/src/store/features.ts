import { produce } from 'immer';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { SSEClient } from '@/lib/api/client';
import { Method } from '@/lib/api/client';
import { API_URL } from '@/lib/constants';
import { BaseFeature } from '@/types/workflowAI/models';
import { FeatureSectionPreview, FeatureSectionResponse } from '../types/workflowAI/models';
import { safeLocalStorageGetItem, safeLocalStorageSetItem } from '@/lib/localStorage';

function isBrowser(): boolean {
  return typeof window !== 'undefined';
}

interface FeaturesState {
  isLoadingFeatureSections: boolean;
  isInitializedFeatureSections: boolean;
  featureSections: Array<FeatureSectionPreview> | undefined;

  isLoadingFeaturesByTag: Record<string, boolean>;
  isInitializedFeaturesByTag: Record<string, boolean>;
  featuresByTag: Record<string, Array<BaseFeature>>;

  isLoadingFeaturesByDomain: Record<string, boolean>;
  isInitializedFeaturesByDomain: Record<string, boolean>;
  featuresByDomain: Record<string, Array<BaseFeature>>;
  companyContextByDomain: Record<string, string>;

  fetchFeatureSections: () => Promise<void>;
  fetchFeaturesByTag: (tag: string) => Promise<void>;
  fetchFeaturesByDomain: (domain: string) => Promise<void>;
}

export const useFeaturesState = create<FeaturesState>((set, get) => ({
  isLoadingFeatureSections: false,
  isInitializedFeatureSections: false,
  featureSections: undefined,

  isLoadingFeaturesByTag: {},
  isInitializedFeaturesByTag: {},
  featuresByTag: {},

  isLoadingFeaturesByDomain: {},
  isInitializedFeaturesByDomain: {},
  featuresByDomain: {},
  companyContextByDomain: {},

  fetchFeatureSections: async () => {
    const isLoading = get().isLoadingFeatureSections;

    if (!!isLoading) {
      return;
    }

    set(
      produce((state: FeaturesState) => {
        state.isLoadingFeatureSections = true;
      })
    );

    const path = `/api/data/features/sections`;

    try {
      const { sections } = await client.get<FeatureSectionResponse>(path);

      set(
        produce((state: FeaturesState) => {
          state.featureSections = sections ?? undefined;
        })
      );
    } finally {
      set(
        produce((state: FeaturesState) => {
          state.isLoadingFeatureSections = false;
          state.isInitializedFeatureSections = true;
        })
      );
    }
  },

  fetchFeaturesByTag: async (tag: string) => {
    const isLoading = get().isLoadingFeaturesByTag[tag];

    if (!!isLoading) {
      return;
    }

    set(
      produce((state: FeaturesState) => {
        state.isLoadingFeaturesByTag[tag] = true;
      })
    );

    const update = (response: { features: Array<BaseFeature> }) => {
      set(
        produce((state: FeaturesState) => {
          state.featuresByTag[tag] = response.features;
        })
      );
    };

    try {
      const response = await SSEClient<Record<string, never>, { features: Array<BaseFeature> }>(
        `${API_URL}/features/search?tags=${tag}`,
        Method.GET,
        {},
        update
      );

      set(
        produce((state: FeaturesState) => {
          state.featuresByTag[tag] = response.features;
        })
      );
    } finally {
      set(
        produce((state: FeaturesState) => {
          state.isLoadingFeaturesByTag[tag] = false;
          state.isInitializedFeaturesByTag[tag] = true;
        })
      );
    }
  },

  fetchFeaturesByDomain: async (domain: string) => {
    const isLoading = get().isLoadingFeaturesByDomain[domain];

    if (!!isLoading) {
      return;
    }

    set(
      produce((state: FeaturesState) => {
        state.isLoadingFeaturesByDomain[domain] = true;
      })
    );

    const update = (response: { company_context: string; features?: Array<BaseFeature> }) => {
      set(
        produce((state: FeaturesState) => {
          state.featuresByDomain[domain] = response?.features ?? [];
          state.companyContextByDomain[domain] = response.company_context;
        })
      );
    };

    try {
      const response = await SSEClient<
        Record<string, never>,
        { company_context: string; features?: Array<BaseFeature> }
      >(`${API_URL}/features/domain/${domain}`, Method.GET, {}, update);

      set(
        produce((state: FeaturesState) => {
          state.featuresByDomain[domain] = response.features ?? [];
        })
      );
    } finally {
      set(
        produce((state: FeaturesState) => {
          state.isLoadingFeaturesByDomain[domain] = false;
          state.isInitializedFeaturesByDomain[domain] = true;
        })
      );
    }
  },
}));

export function buildFeaturePreviewsScopeKey(props: { feature: BaseFeature | undefined }) {
  if (!props.feature) {
    return undefined;
  }
  return `${props.feature.description}-${props.feature.name}-${props.feature.specifications}`;
}

export type FeaturePreview = {
  output_preview: Record<string, unknown>;
  output_schema_preview: Record<string, unknown>;
};

export type FeaturePreviewSchemasRequest = {
  feature: BaseFeature;
  company_context: string | null;
};

interface FeaturePreviewState {
  isLoadingByScope: Map<string, boolean>;
  isInitializedByScope: Map<string, boolean>;
  previewByScope: Map<string, FeaturePreview>;

  fetchFeaturePreviewIfNeeded: (feature: BaseFeature, companyContext: string | undefined) => Promise<void>;
}

const loadPreviewFromStorage = (): Partial<FeaturePreviewState> => {
  if (!isBrowser()) {
    return {};
  }

  try {
    const stored = safeLocalStorageGetItem('featurePreviews');
    if (stored) {
      const parsed = JSON.parse(stored);
      return {
        previewByScope: new Map(Object.entries(parsed.previewByScope || {})),
        isInitializedByScope: new Map(Object.entries(parsed.isInitializedByScope || {})),
      };
    }
  } catch (error) {
    console.error('Error loading feature previews from storage:', error);
  }
  return {};
};

export const useFeaturePreview = create<FeaturePreviewState>((set, get) => ({
  isLoadingByScope: new Map(),
  isInitializedByScope: loadPreviewFromStorage().isInitializedByScope || new Map(),
  previewByScope: loadPreviewFromStorage().previewByScope || new Map(),

  fetchFeaturePreviewIfNeeded: async (feature: BaseFeature, companyContext: string | undefined) => {
    const scopeKey = buildFeaturePreviewsScopeKey({ feature });

    if (!scopeKey) {
      return;
    }

    if (!!get().isLoadingByScope.get(scopeKey)) {
      return;
    }

    if (!!get().isInitializedByScope.get(scopeKey)) {
      return;
    }

    set(
      produce((state: FeaturePreviewState) => {
        if (!scopeKey) {
          return;
        }
        state.isLoadingByScope.set(scopeKey, true);
      })
    );

    const onMessage = (message: FeaturePreview) => {
      set(
        produce((state: FeaturePreviewState) => {
          if (!scopeKey) {
            return;
          }
          state.previewByScope.set(scopeKey, message);
        })
      );
    };

    try {
      const response = await SSEClient<FeaturePreviewSchemasRequest, FeaturePreview>(
        `${API_URL}/features/preview`,
        Method.POST,
        {
          feature: feature,
          company_context: companyContext ?? null,
        },
        onMessage
      );

      set(
        produce((state: FeaturePreviewState) => {
          if (!scopeKey) {
            return;
          }
          state.previewByScope.set(scopeKey, response);
          state.isInitializedByScope.set(scopeKey, true);

          safeLocalStorageSetItem(
            'featurePreviews',
            JSON.stringify({
              previewByScope: Object.fromEntries(state.previewByScope),
              isInitializedByScope: Object.fromEntries(state.isInitializedByScope),
            })
          );
        })
      );
    } finally {
      if (!scopeKey) {
        return;
      }
      set(
        produce((state: FeaturePreviewState) => {
          state.isLoadingByScope.set(scopeKey, false);
          state.isInitializedByScope.set(scopeKey, true);
        })
      );
    }
  },
}));

export type FeatureSchemas = {
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
};

interface FeatureSchemasState {
  isLoadingByScope: Map<string, boolean>;
  isInitializedByScope: Map<string, boolean>;
  schemasByScope: Map<string, FeatureSchemas>;

  fetchFeatureSchemasIfNeeded: (
    feature: BaseFeature,
    companyContext: string | undefined,
    retryIfEmpty?: boolean
  ) => Promise<void>;
}

const loadSchemasFromStorage = (): Partial<FeatureSchemasState> => {
  if (!isBrowser()) {
    return {};
  }

  try {
    const stored = safeLocalStorageGetItem('featurePreviews');
    if (stored) {
      const parsed = JSON.parse(stored);
      return {
        schemasByScope: new Map(Object.entries(parsed.schemasByScope || {})),
        isInitializedByScope: new Map(Object.entries(parsed.isInitializedByScope || {})),
      };
    }
  } catch (error) {
    console.error('Error loading feature schemas from storage:', error);
  }
  return {};
};

export const useFeatureSchemas = create<FeatureSchemasState>((set, get) => ({
  isLoadingByScope: new Map(),
  isInitializedByScope: loadSchemasFromStorage().isInitializedByScope || new Map(),
  schemasByScope: loadSchemasFromStorage().schemasByScope || new Map(),

  fetchFeatureSchemasIfNeeded: async (
    feature: BaseFeature,
    companyContext: string | undefined,
    retryIfEmpty?: boolean
  ) => {
    const scopeKey = buildFeaturePreviewsScopeKey({ feature });

    if (!scopeKey) {
      return;
    }

    if (!!get().isLoadingByScope.get(scopeKey)) {
      return;
    }

    const isInitialized = !!get().isInitializedByScope.get(scopeKey);
    const resultsAreEmpty = !get().schemasByScope.get(scopeKey);
    const retry = retryIfEmpty ?? false;

    if (isInitialized) {
      if (!resultsAreEmpty || !retry) {
        return;
      }
    }

    set(
      produce((state: FeatureSchemasState) => {
        if (!scopeKey) {
          return;
        }
        state.isLoadingByScope.set(scopeKey, true);
        if (resultsAreEmpty) {
          state.isInitializedByScope.set(scopeKey, false);
        }
      })
    );

    try {
      const path = `/api/data/features/schemas`;

      const response = await client.post<FeaturePreviewSchemasRequest, FeatureSchemas>(path, {
        feature: feature,
        company_context: companyContext ?? null,
      });

      set(
        produce((state: FeatureSchemasState) => {
          if (!scopeKey) {
            return;
          }
          state.schemasByScope.set(scopeKey, response);
          state.isInitializedByScope.set(scopeKey, true);

          safeLocalStorageSetItem(
            'featureSchemas',
            JSON.stringify({
              schemasByScope: Object.fromEntries(state.schemasByScope),
              isInitializedByScope: Object.fromEntries(state.isInitializedByScope),
            })
          );
        })
      );
    } finally {
      if (!scopeKey) {
        return;
      }
      set(
        produce((state: FeatureSchemasState) => {
          state.isLoadingByScope.set(scopeKey, false);
          state.isInitializedByScope.set(scopeKey, true);
        })
      );
    }
  },
}));
