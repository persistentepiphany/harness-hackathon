import type { Metadata, Viewport } from 'next';
import { GeistMono } from 'geist/font/mono';
import { GeistSans } from 'geist/font/sans';
import { TopNav } from '@/components/nav/TopNav';
import './globals.css';

export const metadata: Metadata = {
  title: 'Dock Harness',
  description: 'Dock Harness (Prediction Assurance Harness): whether a co-folding or docking result can support a declared claim.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#F7F7F4',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="bg-canvas font-sans text-ink antialiased">
        <div className="flex min-h-screen flex-col text-[13px] leading-[1.45]">
          <TopNav />
          {children}
        </div>
      </body>
    </html>
  );
}
