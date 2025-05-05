import {
  CheckmarkCircle16Filled,
  Sparkle16Filled,
  ThumbDislike16Filled,
  ThumbDislike16Regular,
  ThumbLike16Filled,
  ThumbLike16Regular,
} from '@fluentui/react-icons';
import { Loader2 } from 'lucide-react';
import { useState } from 'react';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { cn } from '@/lib/utils';

export enum AIEvaluationReviewButtonMode {
  NORMAL = 'Normal',
  AI_SELECTED = 'AI Selected',
  USER_SELECTED = 'User Selected',
}

export enum AIEvaluationReviewButtonThumb {
  UP = 'Up',
  DOWN = 'Down',
}

type GetTextColorProps = {
  isHovering: boolean;
  isHoveringSupported: boolean;
  mode: AIEvaluationReviewButtonMode;
  thumb: AIEvaluationReviewButtonThumb;
  disabled: boolean;
};

function getTextColor(props: GetTextColorProps): string {
  const { isHovering, isHoveringSupported, mode, thumb, disabled } = props;

  if (disabled) {
    return 'text-gray-400';
  }

  const isInteractiveHoverState = isHovering && isHoveringSupported && mode === AIEvaluationReviewButtonMode.NORMAL;

  if (thumb === AIEvaluationReviewButtonThumb.UP) {
    return isInteractiveHoverState ? 'text-green-600/80' : 'text-green-600';
  } else {
    return isInteractiveHoverState ? 'text-red-600/80' : 'text-red-600';
  }
}

type GetBorderColorProps = {
  mode: AIEvaluationReviewButtonMode;
  thumb: AIEvaluationReviewButtonThumb;
};

function getBorderColor(props: GetBorderColorProps): string {
  const { mode, thumb } = props;
  if (mode !== AIEvaluationReviewButtonMode.AI_SELECTED) {
    return 'border-transparent';
  }

  return thumb === AIEvaluationReviewButtonThumb.UP ? 'border-green-500' : 'border-red-500';
}

type GetBackgroundColorProps = {
  isHovering: boolean;
  isHoveringSupported: boolean;
  mode: AIEvaluationReviewButtonMode;
  thumb: AIEvaluationReviewButtonThumb;
};

function getBackgroundColor(props: GetBackgroundColorProps): string {
  const { isHovering, isHoveringSupported, mode, thumb } = props;
  const isInteractiveHoverState = isHovering && isHoveringSupported && mode === AIEvaluationReviewButtonMode.NORMAL;

  if (isInteractiveHoverState) {
    return thumb === AIEvaluationReviewButtonThumb.UP ? 'bg-green-200/80' : 'bg-red-200/80';
  }

  if (mode === AIEvaluationReviewButtonMode.USER_SELECTED) {
    return thumb === AIEvaluationReviewButtonThumb.UP ? 'bg-green-200' : 'bg-red-200';
  }

  return 'bg-transparent';
}

type AIEvaluationReviewButtonProps = {
  mode: AIEvaluationReviewButtonMode;
  thumb: AIEvaluationReviewButtonThumb;
  onClick?: () => Promise<void>;
  disabled: boolean;
};

export function AIEvaluationReviewButton(props: AIEvaluationReviewButtonProps) {
  const { mode, thumb, onClick, disabled } = props;
  const [isHovering, setIsHovering] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const isHoveringSupported = mode !== AIEvaluationReviewButtonMode.USER_SELECTED && !!onClick && !disabled;

  // Icon selection
  const icons = {
    [AIEvaluationReviewButtonThumb.UP]: {
      regular: ThumbLike16Regular,
      filled: ThumbLike16Filled,
    },
    [AIEvaluationReviewButtonThumb.DOWN]: {
      regular: ThumbDislike16Regular,
      filled: ThumbDislike16Filled,
    },
  };

  const Icon = mode === AIEvaluationReviewButtonMode.USER_SELECTED ? icons[thumb].filled : icons[thumb].regular;

  // Mini icon selection
  const miniIcons: Record<AIEvaluationReviewButtonMode, React.ElementType | null> = {
    [AIEvaluationReviewButtonMode.AI_SELECTED]: Sparkle16Filled,
    [AIEvaluationReviewButtonMode.USER_SELECTED]: CheckmarkCircle16Filled,
    [AIEvaluationReviewButtonMode.NORMAL]: null,
  };
  const MiniIcon = miniIcons[mode];

  const textColor = getTextColor({
    isHovering,
    isHoveringSupported,
    mode,
    thumb,
    disabled,
  });

  const borderColor = getBorderColor({ mode, thumb });

  const backgroundColor = getBackgroundColor({
    isHovering,
    isHoveringSupported,
    mode,
    thumb,
  });

  const tooltipContent = thumb === AIEvaluationReviewButtonThumb.UP ? 'Mark output as Good' : 'Mark output as Bad';

  const showBackgroundForMiniIcon = mode === AIEvaluationReviewButtonMode.AI_SELECTED;

  const handleClick = async () => {
    if (!onClick || disabled) return;

    setIsLoading(true);
    try {
      await onClick();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <SimpleTooltip
      content={isHoveringSupported ? tooltipContent : undefined}
      tooltipClassName='whitespace-pre-line'
      tooltipDelay={100}
    >
      <div
        className={cn(
          'flex w-7 h-7 items-center justify-center rounded-[2px] border border-dashed relative',
          borderColor,
          backgroundColor,
          textColor,
          isHoveringSupported && 'cursor-pointer'
        )}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
        onClick={handleClick}
      >
        {isLoading ? <Loader2 className='w-4 h-4 animate-spin' /> : <Icon className='w-4 h-4' />}
        {MiniIcon && (
          <div
            className={cn(
              'w-[17px] h-[17px] absolute -top-[6px] -right-[6px] flex items-center justify-center',
              showBackgroundForMiniIcon && 'rounded-full bg-gray-50'
            )}
          >
            <MiniIcon className='w-4 h-4' />
          </div>
        )}
      </div>
    </SimpleTooltip>
  );
}
