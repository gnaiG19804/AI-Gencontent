'use client';

import { useState } from 'react';
import FileUpload from '@/components/FileUpload';
import CSVPreviewTable from '@/components/CSVPreviewTable';
import LogPanel from '@/components/LogPanel';
import { ShoppingBag, RefreshCw } from 'lucide-react';

export default function UploadPage() {
  const [data, setData] = useState<{ products: any[], columns: string[], file_name?: string, total_rows?: number, file?: File } | null>(null);
  const [isPushing, setIsPushing] = useState(false);
  const [showLogs, setShowLogs] = useState(false);

  // Reset to upload state
  const handleReset = () => {
    setData(null);
    setShowLogs(false);
    setIsPushing(false);
  };

  const handlePushToShopify = async () => {
    if (!data || !data.file) {
      alert("No file data found.");
      return;
    }

    setIsPushing(true);
    setShowLogs(true);

    try {
      const formData = new FormData();
      formData.append('file', data.file); // Updated to 'file' to match n8n expectation

      // Trigger the n8n webhook via our proxy to avoid CORS
      // We send FormData, so NO Content-Type header (browser sets it with boundary)
      const res = await fetch('/api/trigger-n8n', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        throw new Error('Failed to trigger n8n workflow');
      }

      // Workflow started successfully
      console.log("n8n workflow triggered with File!");

    } catch (error) {
      console.error("Push Error:", error);
      alert("Failed to trigger n8n workflow. Check console.");
      setIsPushing(false);
    }

    setTimeout(() => setIsPushing(false), 2000);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col p-8">
      <div className="max-w-7xl w-full mx-auto">
        <div className="mb-8 flex justify-between items-end">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Upload & Sync
            </h1>
            <p className="text-gray-600">
              Upload CSV, preview data, and sync to Shopify via n8n.
            </p>
          </div>

          {data && (
            <div className="flex gap-4">
              <button
                onClick={handlePushToShopify}
                disabled={isPushing}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg font-medium"
              >
                {isPushing ? (
                  <>Sending File...</>
                ) : (
                  <>
                    <ShoppingBag className="w-5 h-5" />
                    Push to Shopify
                  </>
                )}
              </button>

              <button
                onClick={handleReset}
                className="flex items-center gap-2 text-sm text-gray-500 hover:text-blue-600 transition-colors border border-gray-200 px-3 py-2 rounded-lg bg-white"
              >
                <RefreshCw className="w-4 h-4" />
                Upload New File
              </button>
            </div>
          )}
        </div>

        {/* State 1: Upload Input (Visible only if NO data) */}
        {!data && (
          <div className="max-w-xl mx-auto mt-12">
            <FileUpload onUploadSuccess={(d) => setData(d)} className="h-auto" />
          </div>
        )}

        {/* State 2: Data & Logs (Visible after upload) */}
        {data && (
          <div className="flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">

            {/* Extended Log Panel - Full Width */}
            {showLogs && (
              <div className="animate-in fade-in duration-300">
                <LogPanel />
              </div>
            )}

            {/* Data Preview Table - Full Width */}
            <div>
              <CSVPreviewTable products={data.products} columns={data.columns} />
            </div>

          </div>
        )}
      </div>
    </div>
  );
}
