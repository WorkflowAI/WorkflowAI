import { cx } from 'class-variance-authority';
import { GeistMono } from 'geist/font/mono';
import { GeistSans } from 'geist/font/sans';
import type { Metadata } from 'next';
import { PageViewTracker } from '@/components/PageViewTracker';
import { ProxyNewAgentModal } from '@/components/ProxyNewAgentModal/ProxyNewAgentModal';
import { AmplitudeConfigurator } from '@/components/amplitude/AmplitudeConfigurator';
import { Toaster } from '@/components/ui/Sonner';
import { AuthWrapper } from '../components/auth/AuthWrapper';
import { Inter, Lato, OpenRunde } from './fonts';
import './globals.css';

export const metadata: Metadata = {
  title: 'WorkflowAI',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang='en'
      className={cx(
        'h-full overflow-clip',
        GeistMono.variable,
        GeistSans.variable,
        OpenRunde.variable,
        Inter.variable,
        Lato.variable
      )}
    >
      <body className='h-full font-lato'>
        <AuthWrapper>
          <AmplitudeConfigurator>
            <PageViewTracker>
              {/* Only add unauthenticated components here. All the authenticated components are in the [tenant]/layout.tsx */}
              <ProxyNewAgentModal />
              {children}
              <Toaster position='bottom-center' />
            </PageViewTracker>
          </AmplitudeConfigurator>
        </AuthWrapper>
      </body>
    </html>
  );
}
