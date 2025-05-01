import { ChevronLeft12Regular, ChevronRight12Regular } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';

type TitleWithHistoryControlsProps = {
  title: string;
  isPreviousOn: boolean;
  isNextOn: boolean;
  onPrevious?: () => void;
  onNext?: () => void;
  tooltipPreviousText: string;
  tooltipNextText: string;
  showHistoryButtons: boolean;
};

export function TitleWithHistoryControls(props: TitleWithHistoryControlsProps) {
  const {
    title,
    isPreviousOn,
    isNextOn,
    onPrevious,
    onNext,
    tooltipPreviousText,
    tooltipNextText,
    showHistoryButtons,
  } = props;

  return (
    <div className='flex flex-row items-center gap-1.5'>
      <div className={cx('text-gray-700 text-[13px] font-semibold')}>{title}</div>

      {showHistoryButtons && (
        <div className='flex flex-row items-center gap-1.5'>
          <SimpleTooltip asChild content={tooltipPreviousText}>
            <div>
              <Button
                variant='newDesignGray'
                icon={<ChevronLeft12Regular className='h-4 w-4 text-gray-900' />}
                onClick={onPrevious}
                disabled={!isPreviousOn}
                size='none'
                className={cx('h-7 w-7', isPreviousOn ? 'opacity-100' : 'opacity-30')}
              />
            </div>
          </SimpleTooltip>
          <SimpleTooltip asChild content={tooltipNextText}>
            <div>
              <Button
                variant='newDesignGray'
                icon={<ChevronRight12Regular className='h-4 w-4 text-gray-900' />}
                onClick={onNext}
                disabled={!isNextOn}
                size='none'
                className={cx('h-7 w-7', isNextOn ? 'opacity-100' : 'opacity-30')}
              />
            </div>
          </SimpleTooltip>
        </div>
      )}
    </div>
  );
}
