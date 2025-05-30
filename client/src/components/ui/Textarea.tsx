import * as React from 'react';
import { useCallback, useEffect, useImperativeHandle } from 'react';
import { cn } from '@/lib/utils/cn';

function useAutoResizeTextarea(ref: React.ForwardedRef<HTMLTextAreaElement>, autoResize: boolean, value: unknown) {
  const textAreaRef = React.useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => textAreaRef.current!);

  const updateTextareaHeight = useCallback(() => {
    const ref = textAreaRef?.current;
    if (ref) {
      const previousHeight = parseFloat(ref.style.height);

      if (!ref.value && ref.placeholder) {
        const clone = ref.cloneNode(true) as HTMLTextAreaElement;
        clone.value = ref.placeholder;
        clone.style.height = '0px';
        clone.style.width = getComputedStyle(ref).width;
        clone.style.position = 'absolute';
        clone.style.visibility = 'hidden';
        ref.parentNode?.appendChild(clone);

        const height = Math.round(clone.scrollHeight + 2) + 'px';
        ref.style.height = height;
        ref.parentNode?.removeChild(clone);
      } else {
        ref.style.height = '0';
        const height = Math.round(ref.scrollHeight + 2) + 'px';
        ref.style.height = height;
      }

      if (Math.abs(Math.round(parseFloat(ref.style.height)) - Math.round(previousHeight)) > 4) {
        ref.scrollTop = Math.round(ref.scrollHeight);
      }
    }
  }, []);

  useEffect(() => {
    if (autoResize) {
      updateTextareaHeight();
    }
  }, [value, autoResize, updateTextareaHeight]);

  useEffect(() => {
    if (!autoResize) return;

    const ref = textAreaRef?.current;
    if (!ref) return;

    updateTextareaHeight();

    // Create resize observer
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.target === ref && entry.contentBoxSize) {
          requestAnimationFrame(updateTextareaHeight);
        }
      }
    });

    // Observe the textarea
    resizeObserver.observe(ref);

    ref.addEventListener('input', updateTextareaHeight);

    return () => {
      resizeObserver.disconnect();
      ref.removeEventListener('input', updateTextareaHeight);
    };
  }, [autoResize, updateTextareaHeight]);

  return textAreaRef;
}

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  autoResize?: boolean;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>((props, ref) => {
  const { autoResize = true, value, className, ...rest } = props;
  const textAreaRef = useAutoResizeTextarea(ref, autoResize, value);

  return (
    <textarea
      className={cn(
        'flex w-full rounded-[2px] border border-gray-300 border-input bg-white px-3 py-2.5 font-lato text-gray-900 text-sm font-normal ring-offset-background placeholder:text-gray-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 resize-none',
        className,
        rest.readOnly ? '' : ''
      )}
      ref={textAreaRef}
      value={value}
      {...rest}
    />
  );
});

Textarea.displayName = 'Textarea';
export { Textarea };
