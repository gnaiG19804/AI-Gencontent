
export const getGeneratedContent = async () => {
  const backendUrl = process.env.PYTHON_BACKEND_URL;
  if (!backendUrl) {
    throw new Error("PYTHON_BACKEND_URL is not set");
  }

  try {
    const response = await fetch(`${backendUrl}/api/content`);
    if (!response.ok) {
      throw new Error(`Python backend error: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Failed to fetch from Python backend:", error);
    throw error;
  }
};
