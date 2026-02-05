import { useLoaderData } from "react-router";
import { getGeneratedContent } from "../services/python.server";

export const loader = async () => {
  try {
    const data = await getGeneratedContent();
    return { status: "success", data };
  } catch (error: any) {
    return { status: "error", message: error.message };
  }
};

export default function TestPythonPublic() {
  const { status, data, message } = useLoaderData<typeof loader>();

  return (
    <div style={{ padding: "20px", fontFamily: "sans-serif" }}>
      <h1>Python Backend Connection Test</h1>
      <p>Status: {status === "success" ? "✅ Connected" : "❌ Failed"}</p>
      {status === "error" && <p style={{ color: "red" }}>Error: {message}</p>}
      {status === "success" && (
        <pre>{JSON.stringify(data, null, 2)}</pre>
      )}
    </div>
  );
}