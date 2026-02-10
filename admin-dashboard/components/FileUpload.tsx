'use client';

import React, { useState, useRef } from 'react';
import { Upload, X, CheckCircle, AlertCircle, FileText } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface FileUploadProps {
  onUploadSuccess: (data: any) => void;
  className?: string;
}

export default function FileUpload({ onUploadSuccess, className }: FileUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setStatus('idle');
      setMessage('');
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setStatus('idle');
      setMessage('');
    }
  };

  const removeFile = () => {
    setFile(null);
    setStatus('idle');
    setMessage('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const uploadFile = async () => {
    if (!file) return;

    // Direct to FastAPI Backend
    const targetUrl = 'http://localhost:8000/upload';

    setIsUploading(true);
    setStatus('idle');
    setMessage('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(targetUrl, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setStatus('success');
        setMessage(`Upload thành công! Đã đọc ${data.total_rows} dòng.`);

        // Pass data up to parent, including the original file
        onUploadSuccess({ ...data, file });

        // setFile(null); // Keep file for visual confirmation
      } else {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Upload failed with status: ${response.status}`);
      }
    } catch (error: any) {
      console.error('Upload error:', error);
      setStatus('error');
      setMessage(error.message || 'Có lỗi xảy ra khi tải lên. Vui lòng thử lại.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className={twMerge("w-full max-w-xl mx-auto p-6 bg-white rounded-xl shadow-sm border border-gray-100 space-y-4", className)}>
      <h2 className="text-xl font-bold text-gray-800 text-center">Tải lên File dữ liệu</h2>

      <div
        className={clsx(
          "relative border-2 border-dashed rounded-lg p-8 transition-colors duration-200 ease-in-out flex flex-col items-center justify-center cursor-pointer",
          isDragging ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-blue-400 hover:bg-gray-50",
          status === 'error' && "border-red-300 bg-red-50",
          status === 'success' && "border-green-300 bg-green-50"
        )}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          type="file"
          className="hidden"
          accept=".csv"
          onChange={handleFileChange}
          ref={fileInputRef}
        />

        {!file ? (
          <>
            <Upload className={clsx("w-12 h-12 mb-3", isDragging ? "text-blue-500" : "text-gray-400")} />
            <p className="text-sm text-gray-600 font-medium">Kéo thả file CSV vào đây</p>
            <p className="text-xs text-gray-400 mt-1">Chỉ hỗ trợ file .csv</p>
          </>
        ) : (
          <div className="flex items-center w-full bg-white p-3 rounded border border-gray-200 shadow-sm relative group">
            <FileText className="w-8 h-8 text-blue-500 mr-3 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{file.name}</p>
              <p className="text-xs text-gray-500">{(file.size / 1024).toFixed(2)} KB</p>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeFile();
              }}
              className="ml-2 text-gray-400 hover:text-red-500 focus:outline-none p-1 rounded-full hover:bg-gray-100 transition-colors"
              disabled={isUploading}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        )}
      </div>

      {status === 'success' && (
        <div className="flex items-start p-3 text-sm text-green-700 bg-green-100 rounded-lg" role="alert">
          <CheckCircle className="w-5 h-5 mr-2 flex-shrink-0" />
          <span>{message}</span>
        </div>
      )}

      {status === 'error' && (
        <div className="flex items-start p-3 text-sm text-red-700 bg-red-100 rounded-lg" role="alert">
          <AlertCircle className="w-5 h-5 mr-2 flex-shrink-0" />
          <span>{message}</span>
        </div>
      )}

      <button
        onClick={uploadFile}
        disabled={!file || isUploading}
        className={clsx(
          "w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white transition-all duration-200",
          !file || isUploading
            ? "bg-gray-400 cursor-not-allowed"
            : "bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        )}
      >
        {isUploading ? (
          <>
            <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Đang phân tích...
          </>
        ) : (
          "Upload"
        )}
      </button>
    </div>
  );
}
