import { useState, useEffect, useRef, useCallback } from "react";
import type { ActionFunctionArgs, LoaderFunctionArgs } from "react-router";
import { useActionData, useNavigation, useSubmit } from "react-router";
import {
  AppProvider,
  Page,
  Layout,
  Card,
  DropZone,
  BlockStack,
  Text,
  Banner,
  Button,
  InlineStack,
  Badge,
  IndexTable,
  Box,
  Thumbnail,
  Pagination,
  Scrollable,
  EmptyState,
  Divider,
  Spinner,
} from "@shopify/polaris";
import enTranslations from "@shopify/polaris/locales/en.json";
import { NoteIcon, UploadIcon, CheckIcon, AlertCircleIcon, RefreshIcon } from "@shopify/polaris-icons";
import { useAppBridge } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { uploadCSV, type CSVUploadResponse } from "../services/csv-upload.server";
import { pushToShopify } from "../services/shopify-push.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  return null;
};

export const action = async ({ request }: ActionFunctionArgs) => {
  await authenticate.admin(request);

  try {
    const formData = await request.formData();
    const actionType = formData.get("actionType") as string;

    if (actionType === "upload") {
      const file = formData.get("file") as File;
      if (!file || file.size === 0) {
        return { action: "upload", status: "error", message: "Please select a valid CSV file" };
      }
      const result = await uploadCSV(file);
      return { action: "upload", status: "success", data: result, timestamp: Date.now() };
    }

    if (actionType === "push") {
      const result = await pushToShopify();
      return { action: "push", status: "success", data: result, timestamp: Date.now() };
    }

    return { status: "error", message: "Invalid action" };
  } catch (error: any) {
    return { status: "error", message: error.message };
  }
};

export default function Index() {
  const actionData = useActionData<typeof action>() as any;
  const navigation = useNavigation();
  const submit = useSubmit();
  const shopify = useAppBridge();

  const [file, setFile] = useState<File | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [persistentUploadData, setPersistentUploadData] = useState<any>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 8;

  const logContainerRef = useRef<HTMLDivElement>(null);

  const isUploading = navigation.state === "submitting" && navigation.formData?.get("actionType") === "upload";
  const isPushing = navigation.state === "submitting" && navigation.formData?.get("actionType") === "push";
  const uploadData = actionData?.action === "upload" ? actionData : null;
  const pushData = actionData?.action === "push" ? actionData : null;

  useEffect(() => {
    if (uploadData?.status === "success" && uploadData?.timestamp) {
      setPersistentUploadData(uploadData);
      setCurrentPage(1);
      shopify.toast.show("File analyzed successfully");
    }
    if (pushData?.status === "success" && pushData?.timestamp) {
      setIsProcessing(false);
      shopify.toast.show("Inventory sync completed");
    }
  }, [uploadData, pushData, shopify]);

  useEffect(() => {
    if (isPushing) {
      setIsProcessing(true);
    }
  }, [isPushing]);

  useEffect(() => {
    const eventSource = new EventSource("http://127.0.0.1:8000/logs");
    eventSource.onopen = () => setIsConnected(true);
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const logMessage = `[${new Date(data.timestamp * 1000).toLocaleTimeString()}] ${data.message}`;
        setLogs((prev) => [...prev, logMessage]);
      } catch (e) {
        console.error("Log parse error", e);
      }
    };
    eventSource.onerror = () => {
      setIsConnected(false);
      eventSource.close();
    };
    return () => eventSource.close();
  }, []);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  const handleDrop = useCallback(
    (_droppedFiles: File[], acceptedFiles: File[], _rejectedFiles: File[]) => {
      setFile(acceptedFiles[0]);
    },
    [],
  );

  const handleUpload = () => {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("actionType", "upload");
    submit(formData, { method: "post", encType: "multipart/form-data" });
  };

  const handlePushToShopify = () => {
    const formData = new FormData();
    formData.append("actionType", "push");
    submit(formData, { method: "post" });
  };

  const displayData = persistentUploadData;
  const hasData = displayData?.status === "success" && displayData?.data;
  const csvData = hasData ? (displayData.data as CSVUploadResponse) : null;
  const allProducts = csvData ? (csvData.products || csvData.data_preview || []) : [];

  const totalPages = Math.ceil(allProducts.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const currentData = allProducts.slice(startIndex, startIndex + itemsPerPage);

  const columnNames = csvData && (Array.isArray(csvData.columns)
    ? (typeof csvData.columns[0] === 'object' ? csvData.columns.map((c: any) => c.name || c) : csvData.columns)
    : (csvData.column_names || []));

  const resourceName = { singular: 'product', plural: 'products' };

  const rowMarkup = currentData.map(
    (row: any, index: number) => (
      <IndexTable.Row id={index.toString()} key={index} position={index}>
        <IndexTable.Cell>
          <Text variant="bodyMd" fontWeight="bold" as="span">{startIndex + index + 1}</Text>
        </IndexTable.Cell>
        {columnNames?.map((col: string, idx: number) => (
          <IndexTable.Cell key={idx}>
            <Box maxWidth="200px" padding="0">
              <Text variant="bodyMd" as="span" truncate>
                {row[col] !== null && row[col] !== undefined ? String(row[col]) : <Text tone="subdued" as="span">-</Text>}
              </Text>
            </Box>
          </IndexTable.Cell>
        ))}
      </IndexTable.Row>
    ),
  );

  return (
    <AppProvider i18n={enTranslations}>
      <Page
        title="test"
        subtitle=""
        primaryAction={
          hasData ? {
            content: isProcessing ? 'Syncing...' : 'Sync to Shopify',
            onAction: handlePushToShopify,
            loading: isProcessing,
            disabled: isProcessing,
            icon: UploadIcon
          } : undefined
        }
      >
        <BlockStack gap="500">

          {actionData?.status === "error" && (
            <Banner tone="critical" title="Operational Error" icon={AlertCircleIcon}>
              <p>{actionData.message}</p>
            </Banner>
          )}

          <Layout>
            <Layout.Section>
              <Card>
                <BlockStack gap="400">
                  <InlineStack align="space-between" blockAlign="center">
                    <Text variant="headingMd" as="h2">Import</Text>
                    {file && <Button variant="plain" onClick={() => setFile(null)} tone="critical">Clear selection</Button>}
                  </InlineStack>

                  <Box paddingBlockStart="200">
                    <DropZone onDrop={handleDrop} allowMultiple={false} accept=".csv" type="file">
                      {file ? (
                        <DropZone.FileUpload actionTitle="Change file" />
                      ) : (
                        <DropZone.FileUpload actionTitle="Select CSV source" actionHint="AI will auto-map your columns" />
                      )}
                    </DropZone>
                  </Box>

                  {file && (
                    <Box background="bg-surface-brand-selected" padding="500" borderRadius="300">
                      <InlineStack align="space-between" blockAlign="center">
                        <InlineStack gap="400" blockAlign="center">
                          <Thumbnail size="small" alt={file.name} source={NoteIcon} />
                          <BlockStack gap="100">
                            <Text variant="bodyMd" fontWeight="bold" as="span">{file.name}</Text>
                            <Text variant="bodySm" tone="subdued" as="span">{(file.size / 1024).toFixed(1)} KB • Local Data</Text>
                          </BlockStack>
                        </InlineStack>
                        <Button
                          variant="primary"
                          onClick={handleUpload}
                          loading={isUploading}
                          icon={RefreshIcon}
                        >
                          Read file
                        </Button>
                      </InlineStack>
                    </Box>
                  )}
                </BlockStack>
              </Card>
            </Layout.Section>

            <Layout.Section variant="oneThird">
              <BlockStack gap="400">
                <Card>
                  <BlockStack gap="300">
                    <Text variant="headingMd" as="h3">Connectivity</Text>
                    <InlineStack gap="300" align="start" blockAlign="center">
                      <Badge tone={isConnected ? 'success' : 'critical'} progress={isConnected ? 'complete' : 'incomplete'}>
                        {isConnected ? 'Active' : 'Offline'}
                      </Badge>
                      {isConnected && (
                        <div style={{
                          width: 10,
                          height: 10,
                          borderRadius: '50%',
                          backgroundColor: '#008060',
                          boxShadow: '0 0 8px #008060',
                          animation: 'pulse 1.5s infinite'
                        }} />
                      )}
                    </InlineStack>
                    <Text tone="subdued" as="p" variant="bodySm">
                      Connected to Python backend services.
                    </Text>
                  </BlockStack>
                </Card>

                {hasData && (
                  <Card background="bg-surface-tertiary">
                    <BlockStack gap="400">
                      <Text variant="headingSm" as="h3" fontWeight="bold">Action Required</Text>
                      <InlineStack align="space-between">
                        <Text as="span">Detected Rows</Text>
                        <Badge tone="info" size="large">{`${allProducts.length}`}</Badge>
                      </InlineStack>
                      <Button fullWidth variant="primary" onClick={handlePushToShopify} loading={isProcessing} icon={UploadIcon}>
                        Upload to Shopify
                      </Button>
                    </BlockStack>
                  </Card>
                )}
              </BlockStack>
            </Layout.Section>
          </Layout>

          <Layout>
            <Layout.Section>
              {!hasData ? (
                <Card padding="2000">
                  <EmptyState
                    heading="No data analyzed yet"
                    action={{
                      content: 'CSV Formatting Guide',
                      url: 'https://help.shopify.com',
                      external: true
                    }}
                    image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                  >
                    <p>Select a product CSV file from your computer to analyze its contents and generate AI content for your Shopify store.</p>
                  </EmptyState>
                </Card>
              ) : (
                <Card padding="0">
                  <Box padding="600">
                    <InlineStack align="space-between" blockAlign="center">
                      <BlockStack gap="100">
                        <Text variant="headingMd" as="h2">Data Preview: {csvData?.file_name}</Text>
                        <Text tone="subdued" as="p" variant="bodySm">Verify your data structure before syncing.</Text>
                      </BlockStack>
                      <Badge tone="attention">{`${allProducts.length} Items found`}</Badge>
                    </InlineStack>
                  </Box>
                  <Divider />
                  <IndexTable
                    resourceName={resourceName}
                    itemCount={allProducts.length}
                    headings={[
                      { title: '#' },
                      ...(columnNames?.map((c: string) => ({ title: c })) || [])
                    ]}
                    selectable={false}
                  >
                    {rowMarkup}
                  </IndexTable>
                  <Divider />
                  <Box padding="400">
                    <InlineStack align="center">
                      <Pagination
                        hasPrevious={currentPage > 1}
                        onPrevious={() => setCurrentPage(p => p - 1)}
                        hasNext={currentPage < totalPages}
                        onNext={() => setCurrentPage(p => p + 1)}
                        label={`Page ${currentPage} of ${totalPages}`}
                      />
                    </InlineStack>
                  </Box>
                </Card>
              )}
            </Layout.Section>
          </Layout>

          <Layout>
            <Layout.Section>
              {(isProcessing || logs.length > 0) && (
                <Card padding="0">
                  <Box padding="600" borderBlockEndWidth="025" borderColor="border-secondary">
                    <InlineStack align="space-between" blockAlign="center">
                      <InlineStack gap="400" blockAlign="center">
                        <Text variant="headingMd" as="h2">Execution Logs</Text>
                        {isProcessing && <Spinner size="small" />}
                      </InlineStack>
                      <Button variant="plain" onClick={() => setLogs([])}>Reset console</Button>
                    </InlineStack>
                  </Box>

                  <Box background="bg-surface-secondary" padding="400">
                    <Scrollable shadow style={{ maxHeight: '350px' }}>
                      <Box padding="100">
                        {logs.length === 0 && (
                          <Box paddingBlock="1000">
                            <Text tone="subdued" as="p" alignment="center">No active background tasks.</Text>
                          </Box>
                        )}
                        <BlockStack gap="200">
                          {logs.map((log, i) => {
                            const isError = log.includes("Error") || log.includes("Failed") || log.includes("❌");
                            const isSuccess = log.includes("Success") || log.includes("✅");

                            return (
                              <Box
                                key={i}
                                padding="300"
                                borderRadius="200"
                                background="bg-surface-secondary"
                              >
                                <InlineStack gap="300" blockAlign="center">
                                  {isError && <AlertCircleIcon style={{ width: 16, color: '#f5222d' }} />}
                                  {isSuccess && <CheckIcon style={{ width: 16, color: '#52c41a' }} />}
                                  <Text
                                    as="span"
                                    variant="bodySm"
                                    fontWeight={isError || isSuccess ? "bold" : "regular"}
                                    tone={isError ? "critical" : isSuccess ? "success" : undefined}
                                  >
                                    {log}
                                  </Text>
                                </InlineStack>
                              </Box>
                            )
                          })}
                          <div ref={logContainerRef} />
                        </BlockStack>
                      </Box>
                    </Scrollable>
                  </Box>
                </Card>
              )}
            </Layout.Section>
          </Layout>

        </BlockStack>
        <style>{`
          @keyframes pulse {
            0% { transform: scale(0.9); opacity: 0.5; }
            50% { transform: scale(1.2); opacity: 1; }
            100% { transform: scale(0.9); opacity: 0.5; }
          }
        `}</style>
      </Page>
    </AppProvider>
  );
}
