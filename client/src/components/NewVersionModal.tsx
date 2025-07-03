'use client';

import { Plus, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { TemperatureSelector } from '@/components/TemperatureSelector/TemperatureSelector';
import { AlertDialog } from '@/components/ui/AlertDialog';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { Textarea } from '@/components/ui/Textarea';
import { TaskSchemaParams } from '@/lib/routeFormatter';
import { Model, UNDEFINED_MODEL } from '@/types/aliases';
import { ModelResponse } from '@/types/workflowAI';
import { ProxyModelCombobox } from './ProxyModelsCombobox/ProxyModelCombobox';

export type TaskVersionEditableProperties = {
  instructions: string;
  temperature: number;
  modelId: Model;
  variantId: string;
};

export const DEFAULT_TASK_VERSION_EDITABLE_PROPERTIES: TaskVersionEditableProperties = {
  instructions: '',
  temperature: 0,
  modelId: UNDEFINED_MODEL,
  variantId: '',
};

function SectionLabelWrapper({ children }: { children: React.ReactNode }) {
  return <div className='mb-2 text-slate-800 font-medium'>{children}</div>;
}

type NewGroupModalProps = TaskSchemaParams & {
  editableProperties: TaskVersionEditableProperties;
  setEditableProperties: (properties: TaskVersionEditableProperties) => void;
  models: ModelResponse[];
  open: boolean;
  onClose: () => void;
  versionWasNotAddedAlertTitle?: string;
  versionWasNotAddedAlertBody?: string;
  addOrReuseVersion: (properties: TaskVersionEditableProperties) => Promise<boolean>;
};

export function NewGroupModal(props: NewGroupModalProps) {
  const {
    open,
    onClose,
    addOrReuseVersion,
    versionWasNotAddedAlertTitle,
    versionWasNotAddedAlertBody,
    editableProperties,
    setEditableProperties,
    models,
  } = props;

  const handleInstructionChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setEditableProperties({
        ...editableProperties,
        instructions: e.target.value,
      });
    },
    [editableProperties, setEditableProperties]
  );

  const onModelChange = useCallback(
    (modelId: Model) => {
      setEditableProperties({
        ...editableProperties,
        modelId,
      });
    },
    [editableProperties, setEditableProperties]
  );

  const onTemperatureChange = useCallback(
    (temperature: number) => {
      setEditableProperties({ ...editableProperties, temperature });
    },
    [editableProperties, setEditableProperties]
  );

  const [showVersionWasNotAddedAlert, setShowVersionWasNotAddedAlert] = useState(false);

  const onAddVersion = useCallback(async () => {
    if (!editableProperties.modelId) return;

    const versionWasAdded = await addOrReuseVersion(editableProperties);

    if (!versionWasAdded) {
      setShowVersionWasNotAddedAlert(true);
      return;
    }

    onClose();
  }, [addOrReuseVersion, editableProperties, onClose]);

  useEffect(() => {
    if (!open) {
      setEditableProperties(DEFAULT_TASK_VERSION_EDITABLE_PROPERTIES);
    }
  }, [setEditableProperties, open]);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className='w-[933px] max-w-[90vw] p-0 overflow-hidden'>
        <div className='max-h-[95vh] flex flex-col overflow-hidden'>
          <div className='flex px-2 py-2 justify-between border-b items-center'>
            <div className='flex gap-3 items-center w-full whitespace-nowrap'>
              <Button variant='outline' icon={<X className='w-4 h-4 text-slate-500' />} onClick={onClose} />
              <h1 className='text-m font-normal'>Add New Version</h1>
              <div className='flex justify-end gap-2 w-full'>
                <Button
                  disabled={!editableProperties.modelId}
                  onClick={onAddVersion}
                  variant='outline'
                  icon={<Plus size={16} />}
                >
                  Add Version
                </Button>
              </div>
            </div>
          </div>
          <div className='flex-1 flex flex-col px-12 py-4 overflow-y-auto'>
            <div className='p-4 text-sm flex flex-col gap-2'>
              <SectionLabelWrapper>1. Select Model</SectionLabelWrapper>
              <div>
                <ProxyModelCombobox
                  value={editableProperties.modelId}
                  onModelChange={onModelChange}
                  models={models}
                  noOptionsMessage='Choose Model'
                  reasoning={undefined}
                />
              </div>
            </div>
            <div className='p-4 text-sm flex flex-col gap-2 max-w-[530px]'>
              <SectionLabelWrapper>2. Instructions</SectionLabelWrapper>
              <Textarea
                className='min-h-[80px]'
                value={editableProperties.instructions}
                onChange={handleInstructionChange}
                placeholder='Add any instructions regarding how you want AI agents to be run on this version...'
              />
            </div>
            <div className='p-4 text-sm flex flex-col gap-2 w-fit'>
              <SectionLabelWrapper>3. Set Temperature</SectionLabelWrapper>
              <TemperatureSelector temperature={editableProperties.temperature} setTemperature={onTemperatureChange} />
            </div>
          </div>
        </div>
        {!!versionWasNotAddedAlertTitle && !!versionWasNotAddedAlertBody && (
          <AlertDialog
            open={showVersionWasNotAddedAlert}
            title={versionWasNotAddedAlertTitle}
            text={versionWasNotAddedAlertBody}
            confrimationText='OK'
            onConfirm={() => setShowVersionWasNotAddedAlert(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
