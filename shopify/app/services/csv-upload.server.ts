export interface CSVUploadResponse {
  status: string;
  file_name: string;
  total_rows: number;
  total_columns: number;
  columns: any[];
  data_preview?: any[];
  column_names?: string[];
  products?: any[];
}

export const uploadCSV = async (file: File): Promise<CSVUploadResponse> => {
  const backendUrl = process.env.PYTHON_BACKEND_URL;
  if (!backendUrl) {
    throw new Error("PYTHON_BACKEND_URL is not set");
  }

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch(`${backendUrl}/upload`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorData.detail || `Upload failed: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error("Failed to upload CSV:", error);
    throw error;
  }
};
