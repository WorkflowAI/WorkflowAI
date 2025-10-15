'use client';

import { DismissFilled, NavigationFilled } from '@fluentui/react-icons';
import { usePathname, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { WorkflowAIIcon } from '@/components/Logos/WorkflowAIIcon';
import { Button } from '@/components/ui/Button';
import { ScrollArea } from '@/components/ui/ScrollArea';
import { ExtendedBordersContainer } from '@/components/v2/ExtendedBordersContainer';
import { NEW_PROXY_AGENT_MODAL_OPEN } from '@/lib/globalModal';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useIsMobile } from '@/lib/hooks/useIsMobile';
import { useRecentTasksHistory } from '@/lib/hooks/useRecentTasksHistory';
import { useLoggedInTenantID, useTaskParams } from '@/lib/hooks/useTaskParams';
import { useParsedSearchParams } from '@/lib/queryString';
import { landingRoute, taskRoute, taskSchemaRoute, tasksRoute } from '@/lib/routeFormatter';
import { getNewestSchemaId, isActiveTask } from '@/lib/taskUtils';
import { CURRENT_TENANT, useOrFetchSchema, useOrFetchTask, useOrFetchTasks } from '@/store';
import { TaskID, TaskSchemaID } from '@/types/aliases';
import { SerializableTask } from '@/types/workflowAI';
import { TasksSection } from '../../../components/TasksSection/TasksSection';
import { checkSchemaForProxy } from '../agents/[taskId]/[taskSchemaId]/proxy-playground/utils';
import { SidebarBottomBar } from './SidebarBottomBar';
import { SectionBlock, SectionItem, generateSections } from './SidebarSections';

export function Sidebar() {
  const { tenant, taskId, taskSchemaId } = useTaskParams();

  const { companyURL } = useParsedSearchParams('companyURL');

  const loggedInTenant = useLoggedInTenantID() ?? tenant;

  const { tasks, isInitialized } = useOrFetchTasks(loggedInTenant ?? CURRENT_TENANT);
  const { task: currentTask } = useOrFetchTask(tenant, taskId);
  const { taskSchema: schema } = useOrFetchSchema(tenant, taskId, taskSchemaId);

  const isProxy = useMemo(() => {
    if (!schema) {
      return false;
    }
    return checkSchemaForProxy(schema);
  }, [schema]);

  const router = useRouter();

  const { recentTasks: recentTasksEntries, addRecentTask } = useRecentTasksHistory(tenant);

  useEffect(() => {
    if (!!taskId && !!taskSchemaId) {
      addRecentTask(taskId, taskSchemaId);
    }
  }, [taskId, taskSchemaId, addRecentTask]);

  const onTryInPlayground = useCallback(
    (task: SerializableTask, taskSchemaId?: TaskSchemaID) => {
      if (!!taskSchemaId) {
        router.push(taskSchemaRoute(tenant, task.id as TaskID, taskSchemaId));
      } else {
        router.push(taskRoute(tenant, task.id as TaskID));
      }
    },
    [router, tenant]
  );

  const pathname = usePathname();

  const { isInDemoMode, isLoggedOut } = useDemoMode();

  const routeBuilderWrapper = useCallback(
    (routeBuilder: SectionItem['routeBuilder']) => {
      if (!routeBuilder) {
        return tasksRoute(loggedInTenant, { [NEW_PROXY_AGENT_MODAL_OPEN]: true });
      }

      if (!!taskId) {
        const schemaId = taskSchemaId ?? getNewestSchemaId(currentTask);

        if (!!schemaId) {
          return routeBuilder(tenant, taskId, schemaId);
        }
      }

      if (!tasks || tasks.length === 0) {
        return tasksRoute(loggedInTenant, { [NEW_PROXY_AGENT_MODAL_OPEN]: true });
      }

      const defaultTask = tasks[0];
      const defaultTaskId = defaultTask.id as TaskID;
      const defaultTaskSchemaId = getNewestSchemaId(defaultTask);

      return routeBuilder(loggedInTenant, defaultTaskId, defaultTaskSchemaId);
    },
    [loggedInTenant, taskId, taskSchemaId, tasks, tenant, currentTask]
  );

  const showActivityIndicator = useMemo(() => {
    return isActiveTask(currentTask);
  }, [currentTask]);

  const sections = useMemo(() => {
    return generateSections(showActivityIndicator, isInDemoMode, isProxy);
  }, [showActivityIndicator, isInDemoMode, isProxy]);

  const routeForLogo = useMemo(() => {
    if (isLoggedOut) {
      return landingRoute({ companyURL });
    }

    return tasksRoute(tenant);
  }, [tenant, isLoggedOut, companyURL]);

  const isMobile = useIsMobile();
  const [isSidebarOpen, setIsSidebarOpen] = useState(!isMobile);

  useEffect(() => {
    setIsSidebarOpen(!isMobile);
  }, [isMobile]);

  useEffect(() => {
    if (isMobile) {
      setIsSidebarOpen(false);
    }
  }, [pathname, isMobile]);

  const margin = !isMobile ? 24 : 0;
  const borderColor = !isMobile ? 'gray-100' : 'clear';

  return (
    <div
      className='flex font-lato sm:pt-6 pt-2 sm:pb-6 pb-0 sm:pl-6 pl-0 z-20 sm:bg-clear bg-custom-gradient-1'
      style={{
        height: isSidebarOpen ? '100%' : 'fit-content',
      }}
    >
      <ExtendedBordersContainer
        className='flex flex-1 flex-col sm:w-[172px] w-full sm:border-0 border-b border-t border-gray-100'
        borderColor={borderColor}
        margin={margin}
      >
        {!!taskId ? (
          <>
            <div className='flex flex-row justify-between items-center'>
              <Button variant='text' size='none' toRoute={routeForLogo}>
                <div className='flex items-center gap-2 sm:px-[10px] sm:py-[10px] py-3 px-4 flex-shrink-0'>
                  <WorkflowAIIcon ratio={1.3} />
                  <span className='font-sans text-[20px] bg-gradient-to-r from-[#8759E3] to-[#4235F8] text-transparent bg-clip-text'>
                    <span className='font-semibold'>Workflow</span>
                    <span className='font-normal'>AI</span>
                  </span>
                </div>
              </Button>
              <Button
                variant='newDesignGray'
                size='none'
                icon={isSidebarOpen ? <DismissFilled className='w-4 h-4' /> : <NavigationFilled className='w-4 h-4' />}
                className='w-9 h-9 sm:mr-2 mr-4 block sm:hidden items-center justify-center'
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              />
            </div>
            {isSidebarOpen && (
              <ScrollArea className='flex-1'>
                <div className='flex flex-col gap-3'>
                  {sections.map((section) => (
                    <SectionBlock
                      key={section.title}
                      title={section.title}
                      items={section.items}
                      showActivityIndicator={section.showActivityIndicator}
                      pathname={pathname}
                      routeBuilderWrapper={routeBuilderWrapper}
                    />
                  ))}
                </div>
              </ScrollArea>
            )}
          </>
        ) : (
          <>
            <TasksSection
              tasks={tasks}
              recentTasksEntries={recentTasksEntries}
              isInitialized={isInitialized}
              onTryInPlayground={onTryInPlayground}
            />
          </>
        )}
        {isSidebarOpen && <SidebarBottomBar isLoggedOut={isLoggedOut} />}
      </ExtendedBordersContainer>
    </div>
  );
}
