import { cx } from 'class-variance-authority';
import { diffLines, diffWords } from 'diff';
import { useMemo } from 'react';
import { CopyButtonWrapper } from '@/components/buttons/CopyTextButton';
import { SimpleTooltip } from '../ui/Tooltip';
import { ValueViewerProps, stringifyNil } from './utils';

function shouldDiffLineForString(text: string) {
  return text?.includes('\n') || text?.includes(' ');
}

type ReadonlyValueProps = Pick<
  ValueViewerProps<string | number | boolean | null | undefined>,
  | 'value'
  | 'referenceValue'
  | 'className'
  | 'schema'
  | 'isError'
  | 'showTypes'
  | 'previewMode'
  | 'showDescriptionExamples'
  | 'hideCopyValue'
> & {
  icon?: React.ReactNode;
};

export function ReadonlyValue(props: ReadonlyValueProps) {
  const {
    value,
    referenceValue,
    className,
    isError,
    showTypes,
    icon,
    previewMode,
    showDescriptionExamples,
    hideCopyValue,
  } = props;
  const text = stringifyNil(value);

  const shouldDiffLine = useMemo(() => {
    if (!referenceValue || typeof referenceValue !== 'string') {
      return false;
    }
    return (
      shouldDiffLineForString(referenceValue) || shouldDiffLineForString(text)
    );
  }, [referenceValue, text]);

  const diff = useMemo(() => {
    if (!referenceValue || typeof referenceValue !== 'string') {
      return null;
    }
    return shouldDiffLine
      ? diffLines(referenceValue, text)
      : diffWords(referenceValue, text);
  }, [text, referenceValue, shouldDiffLine]);

  if (diff) {
    return (
      <div
        className={cx(
          'w-full flex gap-x-1 gap-y-0.5 flex-wrap border border-gray-200 bg-white rounded-[2px] text-[13px] font-medium px-1.5 py-0.5 text-gray-700',
          shouldDiffLine ? 'flex-col items-start' : 'items-center'
        )}
      >
        {diff.map((part) => (
          <span
            key={part.value}
            className={cx('shrink-0 whitespace-break-spaces', {
              'bg-green-100': part.added,
              'bg-red-100': part.removed,
            })}
          >
            {part.value}
          </span>
        ))}
      </div>
    );
  }

  const content = (
    <div
      data-testid='viewer-readonly-value'
      className={cx(
        className,
        'relative min-h-6 flex flex-row gap-1 items-center font-medium text-[13px] px-1.5 py-0.5 border border-gray-200 rounded-[2px] whitespace-pre-line',
        previewMode ? 'bg-gray-50' : 'bg-white',
        {
          'text-gray-400': !isError && previewMode,
          'text-gray-700': !isError && !previewMode,
          'text-red-600 border-red-200': isError,
        }
      )}
      // We are using here style becasue tailwindcc does not support combining: break-word and break-all
      style={{
        wordBreak: 'break-word',
        overflowWrap: 'anywhere',
      }}
    >
      {text}
      {!!icon && icon}
    </div>
  );

  if (!!showTypes) {
    return content;
  }

  if (
    !showTypes &&
    !!showDescriptionExamples &&
    (value === null || value === 'null')
  ) {
    return null;
  }

  if (!!previewMode) {
    return (
      <SimpleTooltip
        content={`This is example data only. You will be able test with more\nrelevant, custom content on Playground after saving your\nschema.`}
        tooltipDelay={200}
        tooltipClassName='whitespace-break-spaces text-center'
      >
        <div className='group flex items-center relative gap-1'>{content}</div>
      </SimpleTooltip>
    );
  }

  if (hideCopyValue) {
    return <div className='group flex items-center gap-1'>{content}</div>;
  }
  return <CopyButtonWrapper text={text}>{content}</CopyButtonWrapper>;
}
