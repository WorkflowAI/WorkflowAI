'use client';

import { usePathname } from 'next/navigation';
import { useMemo } from 'react';
import { DeployVersionModal } from '@/components/DeployIterationModal/DeployVersionModal';
import { NotFound, NotFoundForNotMatchingTenant } from '@/components/NotFound';
import { Loader } from '@/components/ui/Loader';
import { useTaskParams } from '@/lib/hooks/useTaskParams';
import { useIsSameTenant } from '@/lib/hooks/useTaskParams';
import { detectPageIsRequiringTaskSchema, detectPageIsUsingNewDesign } from '@/lib/pageDetection';
import { cn } from '@/lib/utils';
import { useOrFetchTaskSchema } from '@/store/fetchers';
import { TaskID, TaskSchemaID } from '@/types/aliases';

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  // Ok to use default values here, they will never be used
  const { tenant, taskId = '_' as TaskID, taskSchemaId = '_' as TaskSchemaID } = useTaskParams();

  const { taskSchema, isInitialized } = useOrFetchTaskSchema(tenant, taskId, taskSchemaId);

  const isSameTenant = useIsSameTenant();
  const pathname = usePathname();
  const isUsingNewDesign = useMemo(() => detectPageIsUsingNewDesign(pathname), [pathname]);

  //TODO: In the future we should rearchitect a bit and remove the loader completly
  const isRequiringTaskSchema = useMemo(() => detectPageIsRequiringTaskSchema(pathname), [pathname]);

  if (!isInitialized && isRequiringTaskSchema) return <Loader centered />;

  if (taskSchema || !isRequiringTaskSchema) {
    return (
      <div className={cn('w-full h-full', !isUsingNewDesign ? 'pt-[24px] pb-[16px]' : 'overflow-hidden')}>
        {children}
        <DeployVersionModal />
      </div>
    );
  }

  if (!isSameTenant) {
    return <NotFoundForNotMatchingTenant tenant={tenant} />;
  }

  return <NotFound />;
}
