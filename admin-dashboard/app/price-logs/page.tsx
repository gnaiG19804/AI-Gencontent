'use client';

import { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { ChevronLeft, ChevronRight, RefreshCw, Filter, AlertCircle, Search } from 'lucide-react';

interface LogEntry {
  id: number;
  product_id: string;
  variant_id?: string;
  product_title: string;
  old_price: number;
  new_price: number;
  competitor_price: number;
  action: string;
  status: string;
  reason?: string;
  timestamp: string;
}

interface LogResponse {
  total: number;
  limit: number;
  offset: number;
  logs: LogEntry[];
}

export default function PriceLogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [limit] = useState(20);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const offset = (page - 1) * limit;
      let url = `http://localhost:8000/price-sync/logs?limit=${limit}&offset=${offset}`;
      if (statusFilter !== 'ALL') {
        url += `&status=${statusFilter}`;
      }

      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to fetch logs');

      const data: LogResponse = await res.json();
      setLogs(data.logs);
      setTotal(data.total);
    } catch (error) {
      console.error('Error fetching logs:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [page, statusFilter]);

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Price Sync Logs</h1>
          <p className="text-gray-500">History of automated price adjustments</p>
        </div>
        <button
          onClick={fetchLogs}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        {/* Filters */}
        <div className="p-4 border-b border-gray-200 flex gap-4 bg-gray-50">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-500" />
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1); // Reset to first page
              }}
              className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="ALL">All Status</option>
              <option value="SUCCESS">Success</option>
              <option value="PENDING">Pending</option>
              <option value="SKIPPED">Skipped</option>
              <option value="ERROR">Error</option>
            </select>
          </div>
          <div className="ml-auto text-sm text-gray-500 self-center">
            Showing {logs.length} of {total} records
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 text-gray-600 text-xs font-semibold uppercase tracking-wider border-b border-gray-200">
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Product</th>
                <th className="px-6 py-4">Sync Info</th>
                <th className="px-6 py-4">Action</th>
                <th className="px-6 py-4">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loading && logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                    Loading logs...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-gray-500 flex flex-col items-center gap-2">
                    <AlertCircle className="w-8 h-8 text-gray-300" />
                    No logs found.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${log.status === 'SUCCESS' ? 'bg-green-100 text-green-800 border-green-200' :
                          log.status === 'PENDING' ? 'bg-yellow-100 text-yellow-800 border-yellow-200' :
                            log.status === 'SKIPPED' ? 'bg-gray-100 text-gray-800 border-gray-200' :
                              'bg-red-100 text-red-800 border-red-200'
                        }`}>
                        {log.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium text-gray-900 truncate max-w-xs" title={log.product_title || 'Unknown Product'}>
                        {log.product_title || `ID: ${log.product_id}`}
                      </div>
                      <div className="text-xs text-gray-500 font-mono mt-1">
                        {log.variant_id}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-col gap-1 text-sm">
                        <div className="flex justify-between gap-4">
                          <span className="text-gray-500">Old:</span>
                          <span className="font-mono text-gray-700 line-through">${log.old_price?.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between gap-4">
                          <span className="text-gray-500">New:</span>
                          <span className="font-bold text-gray-900">${log.new_price?.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between gap-4">
                          <span className="text-xs text-gray-400">Comp:</span>
                          <span className="text-xs font-mono text-gray-500">${log.competitor_price?.toFixed(2)}</span>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium text-gray-900">{log.action}</div>
                      {log.reason && (
                        <div className="text-xs text-gray-500 mt-1 max-w-[200px] truncate" title={log.reason}>
                          {log.reason}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {format(new Date(log.timestamp), 'MMM d, HH:mm')}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-between items-center bg-gray-50">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="flex items-center gap-1 px-3 py-1 text-sm border border-gray-300 rounded hover:bg-white disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ChevronLeft className="w-4 h-4" /> Previous
          </button>

          <span className="text-sm text-gray-600">
            Page {page} of {totalPages || 1}
          </span>

          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages || totalPages === 0}
            className="flex items-center gap-1 px-3 py-1 text-sm border border-gray-300 rounded hover:bg-white disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
