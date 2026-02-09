import FileUpload from '@/components/FileUpload';

export default function UploadPage() {
  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-4">
      <div className="max-w-2xl w-full text-center mb-8">
        <h1 className="text-3xl font-extrabold text-gray-900 mb-2">
          Hệ thống Tải lên Dữ liệu
        </h1>
        <p className="text-gray-600">
          Vui lòng tải lên file dữ liệu của bạn để hệ thống n8n xử lý.
        </p>
      </div>

      <FileUpload />

      <div className="mt-8 text-sm text-gray-500">
        <p>Hỗ trợ các định dạng: CSV, JSON, XML, Excel...</p>
      </div>
    </div>
  );
}
