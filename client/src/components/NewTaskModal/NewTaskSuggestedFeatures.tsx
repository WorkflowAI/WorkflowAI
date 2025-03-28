import { useEffect, useState } from 'react';
import { SuggestedFeaturesHorizontalSections } from '@/app/landing/sections/SuggestedFeatures/SuggestedFeaturesHorizontalSections';
import { SuggestedFeaturesList } from '@/app/landing/sections/SuggestedFeatures/SuggestedFeaturesList';
import { SuggestedFeaturesSections } from '@/app/landing/sections/SuggestedFeatures/SuggestedFeaturesSections';
import { useOrFetchFeatureSections } from '@/store/fetchers';
import { TagPreview } from '@/types/workflowAI/models';
import { WorkflowAIIcon } from '../Logos/WorkflowAIIcon';
import { NewTaskSuggestedFeaturesHeader } from './NewTaskSuggestedHeaturesHeader';

type NewTaskSuggestedFeaturesProps = {
  userMessage: string;
  setUserMessage: (message: string) => void;
  onSendIteration: () => Promise<void>;
  loading: boolean;
  featureWasSelected: (
    title: string,
    inputSchema: Record<string, unknown>,
    outputSchema: Record<string, unknown>,
    message: string | undefined
  ) => void;
};

export function NewTaskSuggestedFeatures(props: NewTaskSuggestedFeaturesProps) {
  const { userMessage, setUserMessage, onSendIteration, loading, featureWasSelected } = props;
  const [selectedTag, setSelectedTag] = useState<TagPreview | undefined>(undefined);

  const { featureSections, isLoading: featureSectionsAreLoading } = useOrFetchFeatureSections();

  useEffect(() => {
    if (featureSections?.length) {
      setSelectedTag(featureSections[0].tags[0]);
    }
  }, [featureSections, setSelectedTag]);

  return (
    <div className='flex flex-row h-full w-full overflow-hidden border-t border-gray-200 border-dashed'>
      <div className='hidden sm:flex w-[212px] h-full border-r border-gray-200 overflow-y-auto overflow-x-hidden'>
        <SuggestedFeaturesSections
          selectedTag={selectedTag}
          setSelectedTag={setSelectedTag}
          featureSections={featureSections}
          isLoading={featureSectionsAreLoading}
        />
      </div>
      <div className='flex flex-col flex-1 h-full overflow-hidden'>
        <div className='flex px-6 sm:px-16 py-6 sm:py-6 border-b border-gray-100'>
          <div className='flex flex-col gap-6 w-full items-center'>
            <WorkflowAIIcon className='shrink-0 w-16 h-16 mt-6' />

            <div className='text-[18px] text-gray-500 font-normal'>
              What <span className='font-medium text-gray-700'>AI-powered feature</span> do you want to build today?
            </div>
            <NewTaskSuggestedFeaturesHeader
              userMessage={userMessage}
              setUserMessage={setUserMessage}
              onSendIteration={onSendIteration}
              loading={loading}
            />
          </div>
        </div>
        <div className='w-full max-w-full overflow-hidden flex sm:hidden'>
          <SuggestedFeaturesHorizontalSections
            selectedTag={selectedTag}
            setSelectedTag={setSelectedTag}
            featureSections={featureSections}
            isLoading={featureSectionsAreLoading}
          />
        </div>
        <SuggestedFeaturesList tag={selectedTag} featureWasSelected={featureWasSelected} />
      </div>
    </div>
  );
}
