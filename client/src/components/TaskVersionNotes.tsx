import { FileText } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { usePrevious } from '@/lib/hooks/use-previous';
import { TaskVersionNotesInput, TaskVersionNotesInputProps } from './TaskVersionNotesInput';
import { SimpleTooltip } from './ui/Tooltip';

export function TaskVersionNotes(props: TaskVersionNotesInputProps) {
  const { notes, onUpdateNotes, versionId } = props;

  const [displayNotes, setDisplayNotes] = useState(!!notes);
  const [editable, setEditable] = useState(false);
  const activateEdit = useCallback(() => setEditable(true), []);

  const previousVersionId = usePrevious(versionId);
  useEffect(() => {
    if (!versionId || !previousVersionId || versionId === previousVersionId) {
      return;
    }
    setDisplayNotes(!!notes);
  }, [notes, versionId, previousVersionId]);

  // We only display notes if they are not empty
  // We also avoid hiding notes if the user is editing them and they are empty at some point
  if (!displayNotes) {
    return null;
  }

  return (
    <SimpleTooltip content={!editable ? 'Click to Edit' : undefined}>
      <div
        className='flex items-start gap-2 rounded-[2px] border border-gray-200 px-3 py-2 w-full'
        onClick={activateEdit}
      >
        <FileText size={16} className='text-gray-500 translate-y-0.5' />
        {editable ? (
          <TaskVersionNotesInput notes={notes} onUpdateNotes={onUpdateNotes} versionId={versionId} />
        ) : (
          <div className='text-gray-900 text-[13px]'>{notes || '-'}</div>
        )}
      </div>
    </SimpleTooltip>
  );
}
