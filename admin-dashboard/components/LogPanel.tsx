'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Terminal, XCircle, Trash2 } from 'lucide-react';

interface LogMessage {
  message: string;
  level: string;
  timestamp: number;
}

export default function LogPanel() {
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Connect to SSE endpoint
    const eventSource = new EventSource('http://localhost:8000/logs');

    eventSource.onopen = () => {
      console.log('Connected to Log Stream');
      setLogs(prev => [...prev, { message: 'Connected to log stream...', level: 'system', timestamp: Date.now() }]);
    };

    eventSource.onmessage = (event) => {
      try {
        if (!event.data || event.data.trim() === '') return;

        let rawData = event.data;
        if (rawData.startsWith("'") && rawData.endsWith("'")) {
          rawData = rawData.slice(1, -1);
        }

        const logData = JSON.parse(rawData);

        // Filter: Only show logs related to Success/Failure or important Push actions
        // Adjust these keywords based on your backend log messages
        const shouldShow =
          logData.message.includes('Success') ||
          logData.message.includes('Failed') ||
          logData.message.includes('Error') ||
          logData.message.includes('✅') ||
          logData.message.includes('❌');

        if (shouldShow) {
          setLogs(prev => [...prev, logData]);
        }
      } catch (error) {
        console.error('Error parsing log:', event.data, error);
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE Error:', err);
    };

    return () => {
      eventSource.close();
    };
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const clearLogs = () => setLogs([]);

  return (
    <div className="w-full mt-6 bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden flex flex-col h-[400px]">
      <div className="p-3 border-b border-gray-200 bg-gray-50 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-blue-600" />
          <h3 className="font-mono text-sm font-semibold text-gray-700">System Logs</h3>
        </div>
        <button
          onClick={clearLogs}
          className="text-gray-400 hover:text-red-500 transition-colors p-1"
          title="Clear Logs"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-xs md:text-sm bg-white"
      >
        {logs.length === 0 && (
          <div className="text-gray-400 italic text-center mt-10">Waiting for logs...</div>
        )}

        {logs.map((log, idx) => (
          <div key={idx} className="flex gap-2 animate-in fade-in duration-200 border-b border-gray-50 pb-1 last:border-0">
            <span className="text-gray-400 flex-shrink-0 select-none">
              [{new Date(log.timestamp * 1000).toLocaleTimeString()}]
            </span>
            <span className={`break-words ${log.level === 'error' ? 'text-red-600 font-medium' :
                log.level === 'success' ? 'text-green-600 font-medium' :
                  log.level === 'warning' ? 'text-yellow-600' :
                    'text-gray-700'
              }`}>
              {log.message}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
