import { cx } from 'class-variance-authority';
import DOMPurify from 'dompurify';
import { useMemo } from 'react';

type SVGValueContentProps = {
  className: string;
  previewMode: boolean;
  isError: boolean;
  icon: React.ReactNode;
  text: string;
};

export function SVGValueContent(props: SVGValueContentProps) {
  const { className, previewMode, isError, icon, text } = props;

  const isSVG = useMemo(() => {
    if (!text) return false;
    const trimmedText = text.trim();
    return trimmedText.startsWith('<svg') && trimmedText.endsWith('</svg>');
  }, [text]);

  const sanitizedSVG = useMemo(() => {
    if (!isSVG) return null;

    // Add viewBox if not present to support width adjustments for layout
    let svgText = text;
    if (!text.includes('viewBox=')) {
      const widthMatch = text.match(/width="([^"]+)"/);
      const heightMatch = text.match(/height="([^"]+)"/);
      if (widthMatch && heightMatch) {
        const width = widthMatch[1];
        const height = heightMatch[1];
        svgText = text.replace(/<svg/, `<svg viewBox="0 0 ${width} ${height}"`);
      }
    }

    return DOMPurify.sanitize(svgText, {
      USE_PROFILES: { svg: true, svgFilters: true },
      ADD_TAGS: ['use'],
      ADD_ATTR: ['xlink:href'],
    });
  }, [text, isSVG]);

  if (isSVG && sanitizedSVG) {
    return (
      <div
        data-testid='viewer-readonly-value'
        className={cx(
          className,
          'relative min-h-6 px-1.5 py-0.5 border border-gray-200 rounded-[2px] flex items-center w-full',
          previewMode ? 'bg-gray-50' : 'bg-white'
        )}
      >
        <div className='flex-1 w-full overflow-hidden'>
          <div
            className='w-full [&>svg]:block [&>svg]:w-full [&>svg]:h-auto [&>svg]:max-w-full'
            style={{
              width: '100%',
              height: 'auto',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
            }}
            dangerouslySetInnerHTML={{ __html: sanitizedSVG }}
          />
        </div>
        {!!icon && <div className='flex-shrink-0 ml-1'>{icon}</div>}
      </div>
    );
  }

  return (
    <div
      data-testid='viewer-readonly-value'
      className={cx(
        className,
        'relative min-h-6 font-medium text-[13px] px-1.5 py-0.5 border border-gray-200 rounded-[2px] flex items-center',
        previewMode ? 'bg-gray-50' : 'bg-white',
        {
          'text-gray-400': !isError && previewMode,
          'text-gray-700': !isError && !previewMode,
          'text-red-600 border-red-200': isError,
        }
      )}
    >
      <div
        className={cx('flex-1')}
        style={{
          display: 'block',
          WebkitLineClamp: undefined,
          WebkitBoxOrient: undefined,
          wordBreak: 'break-word',
          overflowWrap: 'anywhere',
        }}
      >
        {text}
      </div>
      {!!icon && <div className='flex-shrink-0 ml-1'>{icon}</div>}
    </div>
  );
}
