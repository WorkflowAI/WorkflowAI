import { cx } from 'class-variance-authority';
import { useEffect, useMemo, useRef } from 'react';
import { useFeaturePreview, useFeatureSchemas } from '@/store/features';
import { useOrFetchFeaturesByDomain, useOrFetchFeaturesByTag } from '@/store/fetchers';
import { useOrFetchToken } from '@/store/fetchers';
import { BaseFeature, TagPreview } from '@/types/workflowAI/index';
import { LoadingSuggestedFeaturesListEntry } from './LoadingSuggestedFeaturesListEntry';
import { SuggestedFeaturesCompanyContext } from './SuggestedFeaturesCompanyContext';
import { SuggestedFeaturesListEntry } from './SuggestedFeaturesListEntry';

type SuggestedFeaturesListProps = {
  tag: TagPreview | undefined;
  companyURL?: string;
  featureWasSelected?: (
    title: string,
    inputSchema: Record<string, unknown>,
    outputSchema: Record<string, unknown>,
    message: string | undefined
  ) => void;
};

export function SuggestedFeaturesList(props: SuggestedFeaturesListProps) {
  const { tag, companyURL, featureWasSelected } = props;
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const { token } = useOrFetchToken();

  const isCompanySpecific = tag?.kind === 'company_specific';

  const {
    features: featuresByTag,
    isLoading: featuresByTagAreLoading,
    isInitialized: featuresByTagAreInitialized,
  } = useOrFetchFeaturesByTag(!isCompanySpecific ? tag?.name : undefined, token);

  const {
    features: featuresByDomain,
    companyContext,
    isLoading: featuresByDomainAreLoading,
    isInitialized: featuresByDomainAreInitialized,
  } = useOrFetchFeaturesByDomain(isCompanySpecific ? tag?.name : undefined, token);

  const isLoading = featuresByTagAreLoading || featuresByDomainAreLoading;
  const isInitialized = featuresByTagAreInitialized || featuresByDomainAreInitialized;
  const features: BaseFeature[] | undefined = featuresByTag || featuresByDomain;

  const { fetchFeaturePreviewIfNeeded } = useFeaturePreview();
  const { fetchFeatureSchemasIfNeeded } = useFeatureSchemas();

  const completedFeatures = useMemo(() => {
    if (!features || features.length === 0) {
      return undefined;
    }

    if (!!isInitialized) {
      return features;
    }

    return features.slice(0, -1);
  }, [features, isInitialized]);

  useEffect(() => {
    if (!completedFeatures || completedFeatures.length === 0) {
      return;
    }

    completedFeatures.forEach((feature) => {
      fetchFeaturePreviewIfNeeded(feature, companyContext, token);
      fetchFeatureSchemasIfNeeded(feature, companyContext);
    });
  }, [completedFeatures, companyContext, token, fetchFeaturePreviewIfNeeded, fetchFeatureSchemasIfNeeded]);

  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = 0;
    }
  }, [companyURL]);

  return (
    <div
      ref={scrollContainerRef}
      className='flex flex-col gap-4 w-full h-full sm:pt-8 pt-3 pb-4 sm:pb-0 sm:px-16 px-6 overflow-y-auto'
    >
      <div className='flex flex-col gap-2 w-full'>
        <div className='flex flex-row gap-2 w-full items-center justify-between'>
          <div className='text-gray-400 text-[13px] font-medium hidden sm:block'>{tag?.name}</div>
        </div>
        {isCompanySpecific && <SuggestedFeaturesCompanyContext companyContext={companyContext} isLoading={isLoading} />}
      </div>
      <div className={cx('grid grid-cols-1 sm:grid-cols-1 lg:grid-cols-2 gap-6')}>
        {features?.map((feature) => (
          <SuggestedFeaturesListEntry
            key={feature.name}
            feature={feature}
            companyURL={companyURL}
            featureWasSelected={featureWasSelected}
          />
        ))}
        {isLoading && !features?.length && (
          <>
            <LoadingSuggestedFeaturesListEntry />
            <LoadingSuggestedFeaturesListEntry />
            <LoadingSuggestedFeaturesListEntry />
            <LoadingSuggestedFeaturesListEntry />
          </>
        )}
        {isLoading && !!features?.length && <LoadingSuggestedFeaturesListEntry />}
      </div>
    </div>
  );
}
