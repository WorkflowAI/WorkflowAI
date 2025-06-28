import { Banner } from 'fumadocs-ui/components/banner';
import { RootProvider } from 'fumadocs-ui/provider';
import { Inter } from 'next/font/google';
import type { ReactNode } from 'react';
import './global.css';

const inter = Inter({
  subsets: ['latin'],
});

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <html lang='en' className={inter.className} suppressHydrationWarning>
      <body className='flex flex-col min-h-screen'>
        <Banner>
          <a href='https://workflowai.com' target='_blank' rel='noopener noreferrer' className='underline'>
            WorkflowAI
          </a>
        </Banner>
        <RootProvider>{children}</RootProvider>
      </body>
    </html>
  );
}
