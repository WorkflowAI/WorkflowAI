import { Dismiss12Regular } from '@fluentui/react-icons';
import { useRouter } from 'next/navigation';
import { useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { useRedirectWithParams } from '@/lib/queryString';
import { tasksRoute } from '@/lib/routeFormatter';
import { useOrFetchTasks } from '@/store/fetchers';
import { useIntegrationChat } from '@/store/integrations_messages';
import { TenantID } from '@/types/aliases';
import { NewTaskFlowChoiceSection } from './NewTaskFlowChoiceSection';

type NewTaskFlowChoiceProps = {
  tenant: TenantID | undefined;
  onClose: () => void;
};

export function NewTaskFlowChoice(props: NewTaskFlowChoiceProps) {
  const { onClose, tenant } = props;

  const redirectWithParams = useRedirectWithParams();
  const router = useRouter();

  const { clean } = useIntegrationChat();

  const onCreateFeatureFlow = useCallback(() => {
    redirectWithParams({
      params: {
        flow: 'create',
        integrationId: undefined,
      },
    });
  }, [redirectWithParams]);

  const onRedirectToAgents = useCallback(() => {
    clean();
    const path = tasksRoute(tenant ?? ('_' as TenantID));
    router.push(path);
  }, [tenant, clean, router]);

  const { tasks } = useOrFetchTasks(tenant ?? ('_' as TenantID));

  const areAgentsExisting = useMemo(() => {
    return tasks.length > 0;
  }, [tasks]);

  return (
    <div className='flex flex-col h-full w-full overflow-hidden'>
      <div className='flex items-center px-4 justify-between h-[60px] flex-shrink-0'>
        <div className='flex items-center py-1.5 gap-4 text-gray-700 text-base font-medium font-lato'>
          <Button
            onClick={onClose}
            variant='newDesign'
            icon={<Dismiss12Regular className='w-3 h-3' />}
            className='w-7 h-7'
            size='none'
          />
          What would you like to create?
        </div>
      </div>
      <div className='flex w-full h-full border-t border-dashed border-gray-300'>
        <div className='flex flex-col w-1/2 h-full border-r border-gray-200'>
          <NewTaskFlowChoiceSection
            title='Create New AI Feature'
            subtitle='Build your AI feature directly in WorkflowAI—no coding required. Ideal for product managers, designers, and
            other low-code roles.'
            imageURL='https://workflowai.blob.core.windows.net/workflowai-public/createFlowIllustration.jpg'
          >
            <div className='flex justify-center w-full px-10 pb-10' onClick={onCreateFeatureFlow}>
              <Button variant='newDesignIndigo' className='w-full'>
                Create New AI Feature
              </Button>
            </div>
          </NewTaskFlowChoiceSection>
        </div>
        <div className='flex flex-col w-1/2 h-full'>
          <NewTaskFlowChoiceSection
            title='Import Existing Feature'
            subtitle='Import existing features built in code with your existing integrations. Great for developers.'
            imageURL='https://workflowai.blob.core.windows.net/workflowai-public/OnboardingImport.jpg'
          >
            <div className='flex flex-row gap-4 justify-center w-full px-10 pb-10'>
              <Button
                variant='newDesignIndigo'
                className='w-full'
                toRoute='https://docs.workflowai.com/~/revisions/ft4DWNvzz4kdki59uech/get-started/quickstart/existing-agent'
                openInNewTab={true}
              >
                Read the Documentation
              </Button>
              <SimpleTooltip
                content={areAgentsExisting ? undefined : 'Available after at least one feature is imported'}
                side='top'
                align='center'
                tooltipDelay={100}
              >
                <div className='w-full'>
                  <Button
                    variant='newDesignIndigo'
                    className='w-full'
                    disabled={!areAgentsExisting}
                    onClick={onRedirectToAgents}
                  >
                    Go to Dashboard
                  </Button>
                </div>
              </SimpleTooltip>
            </div>
          </NewTaskFlowChoiceSection>
        </div>
      </div>
    </div>
  );
}
