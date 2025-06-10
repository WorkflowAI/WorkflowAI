import { EditFilled } from '@fluentui/react-icons';
import { useMemo, useState } from 'react';
import { AlertDialog } from '@/components/ui/AlertDialog';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Switch';
import { ProxyImproveMessagesControls } from '../../hooks/useProxyImproveMessages';

type Props = {
  improveMessagesControls: ProxyImproveMessagesControls;
};

export function ProxyDiffsHeader(props: Props) {
  const { improveMessagesControls } = props;

  const numberOfPoints = improveMessagesControls.changelog?.length ?? 0;

  const headerText = useMemo(() => {
    if (!numberOfPoints) return 'Changes';
    return `${numberOfPoints} Changes`;
  }, [numberOfPoints]);

  const [showUndoConfirmation, setShowUndoConfirmation] = useState(false);

  return (
    <div className='flex flex-col w-full h-max text-gray-900 font-normal text-[13px] rounded-[2px] min-h-[60px] border-gray-300 border bg-white/30 whitespace-pre-wrap'>
      <div className='text-gray-900 font-semibold text-[13px] py-2 pl-4 pr-2 bg-gray-50 border-b border-gray-300 flex flex-row w-full gap-1 items-center justify-between'>
        <div>{headerText}</div>
        <div className='flex flex-row gap-2 items-center'>
          <div>Diff</div>
          <Switch checked={improveMessagesControls.showDiffs} onCheckedChange={improveMessagesControls.setShowDiffs} />
        </div>
      </div>
      <div className='flex flex-col gap-1 w-full bg-gray-50 p-3 text-gray-500 shadow-inner'>
        {improveMessagesControls.changelog?.map((line) => (
          <div key={line} className='flex flex-row gap-1.5'>
            <EditFilled className='w-3 h-3 text-gray-500 mt-[3px] flex-shrink-0' />
            {line}
          </div>
        ))}
        <div className='flex flex-row gap-1 pt-2'>
          <Button variant='newDesign' size='sm' onClick={improveMessagesControls.acceptChanges}>
            Okay
          </Button>
          <Button variant='destructive' size='sm' onClick={() => setShowUndoConfirmation(true)}>
            Undo
          </Button>
        </div>
      </div>
      <AlertDialog
        open={showUndoConfirmation}
        title={'Undo Changes'}
        text={'Are you sure you want to undo these changes to the version messages?'}
        confrimationText='Undo'
        destructive={true}
        onCancel={() => setShowUndoConfirmation(false)}
        onConfirm={improveMessagesControls.undoChanges}
      />
    </div>
  );
}
