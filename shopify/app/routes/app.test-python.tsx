import { useLoaderData } from "react-router";
import { authenticate } from "../shopify.server";
import { getGeneratedContent } from "../services/python.server";
import {
  Card,
  Layout,
  Page,
  Text,
  BlockStack,
  Box,
} from "@shopify/polaris";

export const loader = async ({ request }: { request: Request }) => {
  await authenticate.admin(request);

  try {
    const data = await getGeneratedContent();
    return { status: "success", data };
  } catch (error: any) {
    return { status: "error", message: error.message };
  }
};

export default function TestPython() {
  const { status, data, message } = useLoaderData<typeof loader>();

  return (
    <Page title="Test Python Connection">
      <Layout>
        <Layout.Section>
          <Card>
            <BlockStack gap="500">
              <Text as="h2" variant="headingMd">
                Connection Status: {status === "success" ? "✅ Connected" : "❌ Failed"}
              </Text>

              {status === "error" && (
                <Text as="p" tone="critical">
                  Error: {message}
                </Text>
              )}

              {status === "success" && (
                <BlockStack gap="200">
                  <Text as="p">Data received from Python:</Text>
                  <Box
                    padding="400"
                    background="bg-surface-secondary"
                    borderRadius="200"
                    overflowX="scroll"
                  >
                    <pre style={{ margin: 0 }}>
                      <code>{JSON.stringify(data, null, 2)}</code>
                    </pre>
                  </Box>
                </BlockStack>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
