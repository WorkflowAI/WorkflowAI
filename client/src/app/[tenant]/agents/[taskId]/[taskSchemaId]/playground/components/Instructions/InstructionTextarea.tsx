import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { CursorPositionExtension, TagPosition } from './CursorPositionExtension';
import { TagPatternExtension } from './TagPatternExtension';
import { TagPopover } from './TagPopover';
import { changeHTMLToText, changeTextToHTML } from './utils';

type InstructionTextareaProps = {
  text: string;
  onTextChange: (value: string) => void;
  inputKeys: string[] | undefined;
};

export function InstructionTextarea(props: InstructionTextareaProps) {
  const { text, onTextChange, inputKeys } = props;

  const [tagPosition, setTagPosition] = useState<TagPosition | undefined>(undefined);
  const popoverRef = useRef<HTMLDivElement>(null);

  const editor = useEditor({
    editorProps: {
      attributes: {
        class: 'focus:outline-none whitespace-pre-wrap',
      },
    },
    parseOptions: {
      preserveWhitespace: 'full',
    },
    extensions: [
      StarterKit.configure({
        hardBreak: {
          keepMarks: true,
        },
      }),
      TagPatternExtension,
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
        className='flex w-full py-2 px-3 text-gray-900 font-normal text-[13px] rounded-t-[2px] min-h-[60px] border border-gray-300 overflow-y-auto focus-within:ring-inset focus-within:border-gray-900 whitespace-pre-wrap bg-white'
      />
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
            <TagPopover text={tagPosition.tagContent} onAddTag={onAddTag} />
          </div>,
          document.body
        )}
    </div>
  );
}
