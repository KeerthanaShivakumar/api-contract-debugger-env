import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'API Contract Debugger',
  description: 'Interactive debugging environment for API contracts',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
