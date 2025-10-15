'use client';

import { useTaskParams } from '@/lib/hooks/useTaskParams';
import { taskMigrationRoute } from '@/lib/routeFormatter';
import { TenantID } from '@/types/aliases';

type MigrationBannerProps = {
  tenant: TenantID | undefined;
};

export function MigrationBanner({ tenant }: MigrationBannerProps) {
  const { taskId, taskSchemaId } = useTaskParams();

  const migrationUrl = taskId && taskSchemaId && tenant ? taskMigrationRoute(tenant, taskId, taskSchemaId) : null;

  return (
    <div className='bg-yellow-100 border-b border-yellow-200 px-4 py-3 text-sm text-yellow-800'>
      <div className='max-w-7xl mx-auto flex items-center justify-center text-center'>
        <span>
          The WorkflowAI run endpoint and SDK will stop working on January 31st, 2026.
          {migrationUrl ? (
            <>
              {' '}
              Here are the instructions on how to migrate out of WorkflowAI.{' '}
              <a href={migrationUrl} className='underline font-medium hover:text-yellow-900 transition-colors'>
                View migration guide
              </a>
            </>
          ) : (
            ' Select an agent to view migration instructions.'
          )}
        </span>
      </div>
    </div>
  );
}
