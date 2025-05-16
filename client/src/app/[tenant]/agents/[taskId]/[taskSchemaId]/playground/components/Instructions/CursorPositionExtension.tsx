import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';

export type TagPosition = {
  from: number;
  to: number;
  coordinates: { x: number; y: number };
  tagContent: string;
};

export const CursorPositionExtension = Extension.create({
  name: 'cursorPosition',

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('cursorPosition'),
        props: {
          handleKeyDown: (view, event) => {
            const from = view.state.selection.$from;

            // Get text content from the document state
            const text = view.state.doc.textBetween(0, from.pos, '\n');

            // Handle opening tag - only after both { characters
            const beforeCursor = text;
            if (event.key === '{' && beforeCursor.slice(-2) === '{{') {
              const coords = view.coordsAtPos(from.pos);
              const editorRect = view.dom.getBoundingClientRect();
              const lastOpenTag = beforeCursor.lastIndexOf('{{');
              const fromPos = from.pos - (beforeCursor.length - lastOpenTag);

              const customEvent = new CustomEvent('tagPosition', {
                detail: {
                  from: fromPos,
                  to: from.pos,
                  coordinates: {
                    x: coords.left - editorRect.left,
                    y: coords.bottom - editorRect.top,
                  },
                  tagContent: '',
                },
              });
              view.dom.dispatchEvent(customEvent);
            }

            // Handle closing tag
            if (event.key === '}' && beforeCursor.slice(-2) === '}}') {
              const customEvent = new CustomEvent('tagPosition', {
                detail: null,
              });
              view.dom.dispatchEvent(customEvent);
            }
          },
          handleDOMEvents: {
            input: (view) => {
              const from = view.state.selection.$from;

              // Get text content from the document state
              const text = view.state.doc.textBetween(0, from.pos, '\n');

              // Check if we're inside a tag
              const beforeCursor = text;
              const lastOpenTag = beforeCursor.lastIndexOf('{{');
              const lastCloseTag = beforeCursor.lastIndexOf('}}');

              // If there's no open tag, clear the position
              if (lastOpenTag === -1) {
                const customEvent = new CustomEvent('tagPosition', {
                  detail: null,
                });
                view.dom.dispatchEvent(customEvent);
                return;
              }

              // If we have a complete tag (both {{ and }}), clear the position
              if (lastCloseTag > lastOpenTag) {
                const customEvent = new CustomEvent('tagPosition', {
                  detail: null,
                });
                view.dom.dispatchEvent(customEvent);
                return;
              }

              // If we have an open tag and no complete closing tag, show the position
              const coords = view.coordsAtPos(from.pos);
              const editorRect = view.dom.getBoundingClientRect();

              // Calculate the actual document position for the start of the tag
              const fromPos = from.pos - (beforeCursor.length - lastOpenTag);

              // Extract the content between {{ and the current position
              const tagContent = text.slice(lastOpenTag + 2);

              const customEvent = new CustomEvent('tagPosition', {
                detail: {
                  from: fromPos,
                  to: from.pos,
                  coordinates: {
                    x: coords.left - editorRect.left,
                    y: coords.bottom - editorRect.top,
                  },
                  tagContent,
                },
              });
              view.dom.dispatchEvent(customEvent);
            },
          },
        },
      }),
    ];
  },
});
