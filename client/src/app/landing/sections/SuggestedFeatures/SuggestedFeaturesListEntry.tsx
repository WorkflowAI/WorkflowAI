import { cx } from 'class-variance-authority';
import dayjs from 'dayjs';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { useLoggedInTenantID } from '@/lib/hooks/useTaskParams';
import { taskSchemaRoute } from '@/lib/routeFormatter';
import { buildFeaturePreviewsScopeKey, useFeaturePreview, useFeatureSchemas } from '@/store/features';
import { useTasks } from '@/store/task';
import { TaskID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { BaseFeature, CreateAgentRequest } from '@/types/workflowAI/index';
import { SuggestedFeaturesThumbnail } from './SuggestedFeaturesThumbnail';

type SuggestedFeaturesListEntryProps = {
  feature: BaseFeature;
  companyURL: string | undefined;
  featureWasSelected?: (
    title: string,
    inputSchema: Record<string, unknown>,
    outputSchema: Record<string, unknown>,
    message: string | undefined
  ) => void;
};

export function SuggestedFeaturesListEntry(props: SuggestedFeaturesListEntryProps) {
  const { feature, companyURL, featureWasSelected } = props;

  const scopeKey = buildFeaturePreviewsScopeKey({ feature });

  const preview = useFeaturePreview((state) => (!!scopeKey ? state.previewByScope.get(scopeKey) : undefined));

  const schemas = useFeatureSchemas((state) => (!!scopeKey ? state.schemasByScope.get(scopeKey) : undefined));

  const previewInProgress = useFeaturePreview((state) => (!!scopeKey ? state.isLoadingByScope.get(scopeKey) : false));

  const schemasInitialized = useFeatureSchemas((state) =>
    !!scopeKey ? state.isInitializedByScope.get(scopeKey) : false
  );

  const isReadyToCreateTask = !!schemasInitialized;
  const [isHoveringOver, setIsHoveringOver] = useState(false);

  const [waitForSchemas, setWaitForSchemas] = useState(false);
  const [creatingTaskInProgress, setCreatingTaskInProgress] = useState(false);

  const router = useRouter();
  const createTask = useTasks((state) => state.createTask);
  const loggedInTenant = useLoggedInTenantID();

  const { fetchFeatureSchemasIfNeeded } = useFeatureSchemas();

  const onCreateAgent = useCallback(async () => {
    if (!schemas || !schemasInitialized || !schemas) {
      setWaitForSchemas(true);
      fetchFeatureSchemasIfNeeded(feature, companyURL, true);
      return;
    }

    if (creatingTaskInProgress) {
      return;
    }

    setCreatingTaskInProgress(true);

    const name = feature.name ?? `AI agent ${dayjs().format('YYYY-MM-DD-HH-mm-ss')}`;
    const input_schema = schemas.input_schema as Record<string, unknown>;
    const output_schema = schemas.output_schema as Record<string, unknown>;

    if (!!featureWasSelected) {
      featureWasSelected(name, input_schema, output_schema, feature.specifications ?? undefined);
      setTimeout(() => {
        setCreatingTaskInProgress(false);
      }, 4000);
      return;
    }

    const payload: CreateAgentRequest = {
      chat_messages: [],
      name,
      input_schema,
      output_schema,
    };

    const task = await createTask(loggedInTenant, payload);
    const route = taskSchemaRoute(loggedInTenant, task.id as TaskID, `${task.schema_id}` as TaskSchemaID, {
      companyURL: companyURL?.toLowerCase(),
    });

    router.push(route);

    setTimeout(() => {
      setCreatingTaskInProgress(false);
    }, 4000);
  }, [
    companyURL,
    createTask,
    creatingTaskInProgress,
    loggedInTenant,
    router,
    schemas,
    schemasInitialized,
    feature,
    fetchFeatureSchemasIfNeeded,
    featureWasSelected,
  ]);

  // If we are waiting for the schemas to be initialized, and they are, create the task
  useEffect(() => {
    if (isReadyToCreateTask && waitForSchemas) {
      setWaitForSchemas(false);
      if (!!schemas) {
        onCreateAgent();
      }
    }
  }, [isReadyToCreateTask, waitForSchemas, onCreateAgent, schemas]);

  const showButton = isHoveringOver || creatingTaskInProgress || waitForSchemas;
  const showImage = 'image_url' in feature && !!feature.image_url;

  return (
    <div
      className={cx('flex flex-col cursor-pointer')}
      onMouseEnter={() => setIsHoveringOver(true)}
      onMouseLeave={() => setIsHoveringOver(false)}
      onClick={onCreateAgent}
    >
      <div className='relative w-full'>
        <div className='w-full' style={{ paddingTop: '71.49%' }}></div>
        <div className='absolute inset-0 flex items-center justify-center border border-gray-100 rounded-[4px]'>
          {showImage ? (
            <Image src={feature.image_url as string} alt={feature.name} fill className='object-cover' />
          ) : (
            <Image
              src={'https://workflowai.blob.core.windows.net/workflowai-public/gradient.jpg'}
              alt='Landing Page Video Thumbnail'
              className='w-full h-full object-cover opacity-60'
              width={456}
              height={326}
            />
          )}
        </div>
        {!showImage && (
          <div className='absolute inset-0 flex items-center justify-center'>
            <SuggestedFeaturesThumbnail preview={preview} isStreaming={previewInProgress ?? false} />
          </div>
        )}
        {showButton && (
          <div className='absolute inset-0 flex items-center justify-center bg-white/50'>
            <Button variant='newDesign' className='bg-gray-50' loading={creatingTaskInProgress || waitForSchemas}>
              Try This AI Feature
            </Button>
          </div>
        )}
      </div>
      <div className='flex flex-col gap-[2px] w-full py-4'>
        <div className='text-[16px] font-medium text-gray-700'>{feature.name}</div>
        <div className='text-[13px] font-normal text-gray-500'>{feature.description}</div>
      </div>
    </div>
  );
}
