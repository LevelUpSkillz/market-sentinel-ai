import type { Metadata, Viewport } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'Market Sentinel AI · Evidence before action', description: 'Private cryptocurrency investigation, deterministic risk analysis and paper trading.', robots: { index: false, follow: false }, manifest: '/manifest.webmanifest' };
export const viewport: Viewport = { width: 'device-width', initialScale: 1, themeColor: '#0b1110' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
