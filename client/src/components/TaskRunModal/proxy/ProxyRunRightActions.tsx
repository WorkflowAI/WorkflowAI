import { Link16Regular, Play16Regular } from '@fluentui/react-icons';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';

type ProxyRunRightActionsProps = {
  togglePromptModal: () => void;
  playgroundFullRoute: string | undefined;
  copyTaskRunURL: () => void;
};

export function ProxyRunRightActions(props: ProxyRunRightActionsProps) {
  const { togglePromptModal, playgroundFullRoute, copyTaskRunURL } = props;
  return (
    <div className='flex items-center gap-[8px]'>
      {playgroundFullRoute && (
        <SimpleTooltip
          content={
            <div className='text-center'>
              Open the playground with the version
              <br />
              and input from this run prefilled.
            </div>
          }
        >
          <Button toRoute={playgroundFullRoute} icon={<Play16Regular />} variant='newDesign'>
            Load In Playground
          </Button>
        </SimpleTooltip>
      )}
      <Button variant='newDesign' icon={<Link16Regular />} onClick={copyTaskRunURL} className='w-11 h-9 px-0 py-0' />
      <Button variant='newDesign' onClick={togglePromptModal}>
        View Prompt
      </Button>
    </div>
  );
}
