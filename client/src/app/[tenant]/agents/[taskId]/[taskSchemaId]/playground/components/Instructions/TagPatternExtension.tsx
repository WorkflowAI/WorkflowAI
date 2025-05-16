import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';

export const TagPatternExtension = Extension.create({
  name: 'tagPattern',

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('tagPattern'),
        props: {
          decorations: (state) => {
            const { doc } = state;
            const decorations: Decoration[] = [];
            const patterns = [
              /\{\{([^}]+)\}\}/g, // {{text}} pattern
              /@([a-zA-Z0-9_-]+)/g, // @text pattern with hyphens
            ];

            doc.descendants((node, pos) => {
              if (node.isText) {
                patterns.forEach((pattern) => {
                  let match;
                  while ((match = pattern.exec(node.text || '')) !== null) {
                    const start = pos + match.index;
                    const end = start + match[0].length;
                    decorations.push(
                      Decoration.inline(start, end, {
                        class: 'font-bold',
                      })
                    );
                  }
                });
              }
            });

            return DecorationSet.create(doc, decorations);
          },
        },
      }),
    ];
  },
});
