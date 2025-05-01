import { EditFilled } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { diffWords } from 'diff';
import { useEffect, useMemo, useState } from 'react';
import { AlertDialog } from '@/components/ui/AlertDialog';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Switch';

type InstructionsDiffViewerProps = {
  instructions: string;
  oldInstructions: string;
  improveVersionChangelog: string[] | undefined;
  resetImprovedInstructions: () => void;
  approveImprovedInstructions: () => void;
};

export function InstructionsDiffViewer(props: InstructionsDiffViewerProps) {
  const {
    instructions,
    oldInstructions,
    improveVersionChangelog,
    resetImprovedInstructions,
    approveImprovedInstructions,
  } = props;

  const diff = useMemo(() => {
    return diffWords(oldInstructions, instructions);
  }, [instructions, oldInstructions]);

  const numberOfPoints = improveVersionChangelog?.length ?? 0;

  const headerText = useMemo(() => {
    if (!numberOfPoints) return 'Changes';
    return `${numberOfPoints} Changes`;
  }, [numberOfPoints]);

  const [showUndoConfirmation, setShowUndoConfirmation] = useState(false);
  const [diffsAreOn, setDiffsAreOn] = useState(true);

  useEffect(() => {
    setDiffsAreOn(true);
  }, [instructions]);

  return (
    <div className='text-gray-900 font-normal text-[13px] rounded-[2px] min-h-[60px] border-gray-300 border overflow-y-auto bg-white whitespace-pre-wrap'>
      <div className='text-gray-900 font-semibold text-[13px] py-2 pl-4 pr-2 bg-gray-50 border-b border-gray-300 flex flex-row w-full gap-1 items-center justify-between'>
        <div>{headerText}</div>
        <div className='flex flex-row gap-2 items-center'>
          <div>Diff</div>
          <Switch checked={diffsAreOn} onCheckedChange={setDiffsAreOn} />
        </div>
      </div>
      <div className='flex flex-col gap-1 w-full bg-gray-50 p-3 border-b border-gray-300 text-gray-500 shadow-inner'>
        {improveVersionChangelog?.map((line) => (
          <div key={line} className='flex flex-row gap-1.5'>
            <EditFilled className='w-3 h-3 text-gray-500 mt-[3px]' />
            {line}
          </div>
        ))}
        <div className='flex flex-row gap-1 pt-2'>
          <Button variant='newDesign' size='sm' onClick={approveImprovedInstructions}>
            Okay
          </Button>
          <Button variant='destructive' size='sm' onClick={() => setShowUndoConfirmation(true)}>
            Undo
          </Button>
        </div>
      </div>
      {diffsAreOn ? (
        <div className='p-3'>
          {diff.map((part, index) => {
            if (!part.value) return null;
            return (
              <span
                key={index}
                className={cx({
                  'bg-green-100 text-green-800 rounded px-0.5': part.added,
                  'bg-red-100 text-red-800 rounded px-0.5': part.removed,
                })}
              >
                {part.value}
              </span>
            );
          })}
        </div>
      ) : (
        <div className='p-3'>{instructions}</div>
      )}
      <AlertDialog
        open={showUndoConfirmation}
        title={'Undo Changes'}
        text={'Are you sure you want to undo these changes to the instructions?'}
        confrimationText='Undo'
        destructive={true}
        onCancel={() => setShowUndoConfirmation(false)}
        onConfirm={resetImprovedInstructions}
      />
    </div>
  );
}
