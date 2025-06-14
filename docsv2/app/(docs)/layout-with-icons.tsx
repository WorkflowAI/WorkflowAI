import { DocsLayout, type DocsLayoutProps } from 'fumadocs-ui/layouts/docs';
import type { ReactNode } from 'react';
import { baseOptions } from '@/app/layout.config';
import { source } from '@/lib/source';
import { FileText, BookOpen, Code } from 'lucide-react';

const docsOptions: DocsLayoutProps = {
  ...baseOptions,
  tree: source.pageTree,
  sidebar: {
    tabs: {
      transform: (option) => {
        // Add custom icons based on the tab title
        const icons: Record<string, ReactNode> = {
          'Components': <FileText className="w-4 h-4" />,
          'Guides': <BookOpen className="w-4 h-4" />,
          'API Reference': <Code className="w-4 h-4" />,
        };
        
        return {
          ...option,
          icon: icons[String(option.title)] || null,
        };
      },
    },
    // Optional: Add a banner above the sidebar
    banner: (
      <div className="p-2 bg-blue-50 dark:bg-blue-950 rounded-md text-sm">
        📚 Welcome to our documentation!
      </div>
    ),
  },
};

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <DocsLayout {...docsOptions}>
      {children}
    </DocsLayout>
  );
} 