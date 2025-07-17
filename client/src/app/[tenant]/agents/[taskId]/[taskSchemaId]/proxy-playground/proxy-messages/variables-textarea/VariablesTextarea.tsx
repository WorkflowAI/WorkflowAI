import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { CursorPositionExtension, TagPosition } from './CursorPositionExtension';
import { ErrorTagPopover } from './ErrorTagPopover';
import { TagPatternExtension } from './TagPatternExtension';
import { TagPopover } from './TagPopover';
import { changeHTMLToText, changeTextToHTML } from './utils';

type Props = {
  text: string;
  onTextChange: (value: string) => void;
  placeholder?: string;
  readOnly?: boolean;
  inputVariblesKeys?: string[];
  supportInputVaribles?: boolean;
  onFocus?: () => void;
  onBlur?: () => void;
  autofocus?: boolean;
};

export function VariablesTextarea(props: Props) {
  const {
    text,
    onTextChange,
    placeholder,
    readOnly,
    inputVariblesKeys,
    supportInputVaribles = true,
    onFocus,
    onBlur,
    autofocus = false,
  } = props;

  const [tagPosition, setTagPosition] = useState<TagPosition | undefined>(undefined);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!tagPosition) return;

      const popoverElement = document.querySelector('.tag-popover');
      if (!popoverElement) return;

      if (e.key === 'Tab' || e.key === 'Enter') {
        e.preventDefault();
        const firstTag = popoverElement.querySelector('.tag-item');
        if (firstTag instanceof HTMLElement) {
          firstTag.click();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [tagPosition]);

  const tagClass = useMemo(() => {
    if (supportInputVaribles) {
      return 'font-bold';
    }
    return 'text-red-500 font-medium underline decoration-wavy decoration-red-500 underline-offset-4';
  }, [supportInputVaribles]);

  const editor = useEditor({
    editorProps: {
      attributes: {
        class: 'focus:outline-none whitespace-pre-wrap w-full',
        autocorrect: 'off',
        autocapitalize: 'off',
        spellcheck: 'false',
      },
      handleKeyDown: (view, event) => {
        if (event.key === 'Enter' && tagPosition) {
          event.preventDefault();
          return true;
        }
        return false;
      },
    },
    editable: !readOnly,
    parseOptions: {
      preserveWhitespace: 'full',
    },
    autofocus: autofocus,
    extensions: [
      StarterKit.configure({
        hardBreak: {
          keepMarks: true,
        },
      }),
      TagPatternExtension.configure({
        tagClass: tagClass,
      }),
      CursorPositionExtension,
    ],
    content: changeTextToHTML(text),
    onUpdate: ({ editor }) => {
      const newHTML = editor.getHTML();
      const oldHTML = changeTextToHTML(text);
      if (newHTML !== oldHTML) {
        const newText = changeHTMLToText(newHTML);
        onTextChange(newText);
      }
    },
    immediatelyRender: false,
  });

  // When streaming new text we need to make sure to convert to HTML
  useEffect(() => {
    if (!editor) return;
    if (document.activeElement === editor.view.dom) return;

    const newHTML = changeTextToHTML(text);
    const oldHTML = editor.getHTML();

    if (newHTML === oldHTML) return;

    editor.commands.setContent(newHTML, false, {
      preserveWhitespace: 'full',
    });
  }, [editor, text]);

  // When the cursor is moved we need to update the tag position
  useEffect(() => {
    if (editor) {
      const handleTagPosition = (event: CustomEvent<TagPosition>) => {
        if (event.detail) {
          const editorRect = editor.view.dom.getBoundingClientRect();
          const absoluteX = editorRect.left + event.detail.coordinates.x;
          const absoluteY = editorRect.top + event.detail.coordinates.y;

          setTagPosition({
            ...event.detail,
            coordinates: {
              x: absoluteX,
              y: absoluteY,
            },
          });
        } else {
          setTagPosition(undefined);
        }
      };

      editor.view.dom.addEventListener('tagPosition', handleTagPosition as EventListener);
      return () => {
        editor.view.dom.removeEventListener('tagPosition', handleTagPosition as EventListener);
      };
    }
  }, [editor]);

  // When the tag position is set we need to make sure to close the popover when the user clicks outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setTagPosition(undefined);
      }
    };

    if (tagPosition) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [tagPosition]);

  const onAddTag = (tag: string) => {
    if (!editor || !tagPosition) return;

    // Delete the existing tag pattern
    editor.commands.deleteRange({
      from: tagPosition.from,
      to: tagPosition.to,
    });

    // Insert the new tag
    editor.commands.insertContent(`{{${tag}}}`);

    // Close the popover
    setTagPosition(undefined);
  };

  return (
    <div className='flex w-full relative'>
      <EditorContent
        editor={editor}
        className='flex w-full px-3 text-gray-900 font-normal text-[13px] rounded-t-[2px] whitespace-pre-wrap'
        onFocus={onFocus}
        onBlur={onBlur}
      />
      {editor?.isEmpty && placeholder && (
        <div className='absolute top-0 left-3 text-gray-500 text-[13px] pointer-events-none'>{placeholder}</div>
      )}
      {tagPosition &&
        createPortal(
          <div
            ref={popoverRef}
            className='fixed flex p-1'
            style={{
              left: tagPosition.coordinates.x,
              top: tagPosition.coordinates.y,
              transform: 'translateX(-50%)',
            }}
          >
            {supportInputVaribles ? (
              <TagPopover text={tagPosition.tagContent} onAddTag={onAddTag} tags={inputVariblesKeys} />
            ) : (
              <ErrorTagPopover />
            )}
          </div>,
          document.body
        )}
    </div>
  );
}
