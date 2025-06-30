import { loader } from 'fumadocs-core/source';
import { BookMarked, BookOpen, Code, FileCode, FileText, Plug, Sparkles, TestTube } from 'lucide-react';
import { createElement } from 'react';
import { docs } from '@/.source';

// Icon mapping
const icons: Record<string, React.ElementType> = {
  BookOpen,
  TestTube,
  Plug,
  BookMarked,
  FileText,
  Code,
  Sparkles,
  FileCode,
};

// See https://fumadocs.vercel.app/docs/headless/source-api for more info
export const source = loader({
  // it assigns a URL to your pages
  baseUrl: '/',
  source: docs.toFumadocsSource(),
  icon(name) {
    if (!name || !(name in icons)) return undefined;
    const Icon = icons[name];
    return createElement(Icon);
  },
});
