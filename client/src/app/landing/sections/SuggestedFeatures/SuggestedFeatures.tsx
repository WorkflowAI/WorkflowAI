import { capitalize } from 'lodash';
import { useEffect, useMemo, useState } from 'react';
import { useOrFetchFeatureSections } from '@/store/fetchers';
import { TagPreview } from '@/types/workflowAI/models';
import { SuggestedFeaturesHorizontalSections } from './SuggestedFeaturesHorizontalSections';
import { SuggestedFeaturesList } from './SuggestedFeaturesList';
import { SuggestedFeaturesSearch } from './SuggestedFeaturesSearch';
import { SuggestedFeaturesSections } from './SuggestedFeaturesSections';

type SuggestedFeaturesProps = {
  companyURL?: string;
  setCompanyURL?: (companyURL: string) => void;
  hideSidebar: boolean;
};

export function SuggestedFeatures(props: SuggestedFeaturesProps) {
  const { companyURL, setCompanyURL, hideSidebar } = props;

  const [selectedTag, setSelectedTag] = useState<TagPreview | undefined>(undefined);

  const { featureSections, isLoading: featureSectionsAreLoading } = useOrFetchFeatureSections();

  const modifiedFeatureSections = useMemo(() => {
    if (!featureSections) {
      return undefined;
    }

    return featureSections.map((section) => {
      const newTags = [...section.tags];

      if (!!companyURL) {
        // Find and replace company_specific tag
        const companySpecificIndex = newTags.findIndex((tag) => tag.kind === 'company_specific');
        if (companySpecificIndex !== -1) {
          const newTag: TagPreview = {
            name: capitalize(companyURL),
            kind: 'company_specific',
          };
          newTags[companySpecificIndex] = newTag;
          setSelectedTag(newTag);
        }
      } else {
        // Remove company_specific tags with empty name or 'For You'
        const filteredTags = newTags.filter(
          (tag) => !(tag.kind === 'company_specific' && (tag.name === '' || tag.name === 'For You'))
        );
        return { ...section, tags: filteredTags };
      }

      return { ...section, tags: newTags };
    });
  }, [featureSections, companyURL, setSelectedTag]);

  useEffect(() => {
    if (modifiedFeatureSections?.length) {
      setSelectedTag(modifiedFeatureSections[0].tags[0]);
    }
  }, [modifiedFeatureSections, setSelectedTag]);

  return (
    <div className='flex flex-row h-full w-full overflow-hidden'>
      {!hideSidebar && (
        <div className='hidden sm:flex w-[212px] h-full border-r border-gray-200 bg-custom-gradient-1 overflow-y-auto overflow-x-hidden'>
          <SuggestedFeaturesSections
            selectedTag={selectedTag}
            setSelectedTag={setSelectedTag}
            featureSections={modifiedFeatureSections}
            isLoading={featureSectionsAreLoading}
          />
        </div>
      )}
      <div className='flex flex-col flex-1 h-full overflow-hidden'>
        <div className='flex px-6 sm:px-16 py-6 sm:py-10 border-b border-gray-100'>
          <div className='flex flex-col gap-4 w-full sm:items-start items-center'>
            <div className='text-[18px] text-gray-500 font-normal'>
              What Al features would make your users say <span className='font-semibold'>&apos;wow&apos;</span>?
            </div>
            <SuggestedFeaturesSearch companyURL={companyURL} setCompanyURL={setCompanyURL} />
          </div>
        </div>
        {!hideSidebar && (
          <div className='pt-6 w-full max-w-full overflow-hidden flex sm:hidden shrink-0'>
            <SuggestedFeaturesHorizontalSections
              selectedTag={selectedTag}
              setSelectedTag={setSelectedTag}
              featureSections={modifiedFeatureSections}
              isLoading={featureSectionsAreLoading}
            />
          </div>
        )}
        <SuggestedFeaturesList tag={selectedTag} companyURL={companyURL} />
      </div>
    </div>
  );
}
