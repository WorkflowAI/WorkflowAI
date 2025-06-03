import { Dismiss12Regular } from '@fluentui/react-icons';
import { useCallback, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { formatSemverVersion } from '@/lib/versionUtils';
import { useOrFetchVersion } from '@/store/fetchers';
import { TaskID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';
import { CodeLanguage } from '@/types/snippets';
import { VersionEnvironment } from '@/types/workflowAI';
import { ApiContainer } from './ApiContainer';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  versionId?: string;
  setVersionId: (versionId: string | undefined) => void;
};

export function CodeModal(props: Props) {
  const { tenant, taskId, versionId, setVersionId } = props;

  const { version: versionForCodeModal } = useOrFetchVersion(tenant, taskId, versionId);
  const [selectedEnvironment, setSelectedEnvironment] = useState<VersionEnvironment | undefined>(undefined);
  const [selectedLanguage, setSelectedLanguage] = useState<CodeLanguage | undefined>(undefined);
  const [selectedIntegrationId, setSelectedIntegrationId] = useState<string | undefined>(undefined);

  const setSelectedEnvironmentAndVersionId = useCallback(
    (environment: VersionEnvironment | undefined, versionId: string | undefined) => {
      setSelectedEnvironment(environment);
      setVersionId(versionId);
    },
    [setVersionId, setSelectedEnvironment]
  );

  const onSelectVersionId = useCallback(
    (versionId: string | undefined) => {
      setSelectedEnvironment(undefined);
      setVersionId(versionId);
    },
    [setVersionId]
  );

  if (!versionId) {
    return null;
  }

  return (
    <Dialog open={!!versionId} onOpenChange={() => setVersionId(undefined)}>
      <DialogContent className='max-w-[90vw] w-[90vw] max-h-[90vh] h-[90vh] p-0 bg-custom-gradient-1 rounded-[2px] border border-gray-300'>
        <div className='flex flex-col h-full w-full overflow-hidden'>
          <div className='flex items-center px-4 justify-between h-[52px] flex-shrink-0 border-b border-gray-200 border-dashed'>
            <div className='flex items-center gap-4 text-gray-900 text-[16px] font-semibold'>
              <Button
                onClick={() => setVersionId(undefined)}
                variant='newDesign'
                icon={<Dismiss12Regular className='w-3 h-3' />}
                className='w-7 h-7'
                size='none'
              />
              View Code for Version {formatSemverVersion(versionForCodeModal)}
            </div>
          </div>
          <div className='flex flex-row w-full h-[calc(100%-52px)] overflow-hidden'>
            <ApiContainer
              tenant={tenant}
              taskId={taskId}
              setSelectedVersionId={onSelectVersionId}
              setSelectedEnvironment={setSelectedEnvironmentAndVersionId}
              setSelectedLanguage={setSelectedLanguage}
              setSelectedIntegrationId={setSelectedIntegrationId}
              selectedVersionId={versionId}
              selectedEnvironment={selectedEnvironment}
              selectedLanguage={selectedLanguage}
              selectedIntegrationId={selectedIntegrationId}
            />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
