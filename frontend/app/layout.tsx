import type { Metadata, Viewport } from 'next';
import './globals.css';
import './premium.css';
import './mission.css';
export const metadata: Metadata = { title: 'Market Sentinel AI · Evidence before action', description: 'Private market intelligence, public trader investigations and individually approved Kraken spot orders.', robots: { index: false, follow: false }, manifest: '/manifest.webmanifest' };
export const viewport: Viewport = { width: 'device-width', initialScale: 1, themeColor: '#090e19' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
