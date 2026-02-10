'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { UploadCloud, FileText, CheckCircle, BarChart3, Settings } from 'lucide-react';
import { clsx } from 'clsx';

export default function Sidebar() {
  const pathname = usePathname();

  const links = [
    { href: '/upload', label: 'Upload & Sync', icon: UploadCloud },
    { href: '/price-logs', label: 'Price Sync Logs', icon: FileText },
  ];

  return (
    <div className="w-64 bg-slate-900 text-white min-h-screen flex flex-col fixed left-0 top-0 bottom-0 z-50">
      <div className="p-6 border-b border-slate-700">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <CheckCircle className="text-green-400" />
          Dashboard
        </h1>
      </div>

      <nav className="flex-1 p-4 space-y-2">
        {links.map((link) => {
          const Icon = link.icon;
          const isActive = pathname === link.href || pathname.startsWith(link.href);

          return (
            <Link
              key={link.href}
              href={link.href}
              className={clsx(
                "flex items-center gap-3 px-4 py-3 rounded-lg transition-colors font-medium",
                isActive
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-900/50"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              )}
            >
              <Icon className="w-5 h-5" />
              {link.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-slate-700">
        <div className="text-xs text-slate-500 text-center">
          v2.0.0
        </div>
      </div>
    </div>
  );
}
