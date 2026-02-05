import { useState, useEffect, useRef, useCallback } from "react";
import type { ActionFunctionArgs } from "react-router";
import { useActionData, Form, useNavigation, useSubmit } from "react-router";
import {
  Page,
  Layout,
  LegacyCard,
  DropZone,
  BlockStack,
  Text,
  Banner,
  Button,
  InlineStack,
  Badge,
  IndexTable,
  AppProvider,
  Box,
  Thumbnail,
  CalloutCard,
  useIndexResourceState,
  Pagination,
  Spinner,
  Scrollable,
} from "@shopify/polaris";
import { NoteIcon, UploadIcon } from "@shopify/polaris-icons";
import enTranslations from "@shopify/polaris/locales/en.json";
import { uploadCSV, type CSVUploadResponse } from "../services/csv-upload.server";
import { pushToShopify } from "../services/shopify-push.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const formData = await request.formData();
    const actionType = formData.get("actionType") as string;

    if (actionType === "upload") {
      const file = formData.get("file") as File;
      if (!file || file.size === 0) {
        return { action: "upload", status: "error", message: "Please select a valid CSV file" };
      }
      const result = await uploadCSV(file);
      return { action: "upload", status: "success", data: result };
    }

    if (actionType === "push") {
      const result = await pushToShopify();
      return { action: "push", status: "success", data: result };
    }

    return { status: "error", message: "Invalid action" };
  } catch (error: any) {
    return { status: "error", message: error.message };
  }
};

export default function UploadCSVPublic() {
  const actionData = useActionData<typeof action>() as any;
  const navigation = useNavigation();
  const submit = useSubmit();

  const [file, setFile] = useState<File | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [persistentUploadData, setPersistentUploadData] = useState<any>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  const logContainerRef = useRef<HTMLDivElement>(null);

  const isUploading = navigation.state === "submitting";
  const uploadData = actionData?.action === "upload" ? actionData : null;
  const pushData = actionData?.action === "push" ? actionData : null;

  // Persist upload data when success
  useEffect(() => {
    if (uploadData?.status === "success") {
      setPersistentUploadData(uploadData);
      setCurrentPage(1);
    }
  }, [uploadData]);

  // Handle processing state
  useEffect(() => {
    if (navigation.state === "submitting" && navigation.formData?.get("actionType") === "push") {
      setIsProcessing(true);
    }
  }, [navigation.state, navigation.formData]);

  // SSE Connection
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

  // Auto-scroll logs
  useEffect(() => {
    // Polaris Scrollable doesn't easily expose ref to DOM node for scrollTop, 
    // but if we use a simple div inside Scrollable, we can ref it.
    if (logContainerRef.current) {
      logContainerRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  // File Upload Handlers
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

  // Prepare Data for Table
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

  // Table Configuration
  const resourceName = {
    singular: 'product',
    plural: 'products',
  };

  const rowMarkup = currentData.map(
    (row: any, index: number) => (
      <IndexTable.Row id={index.toString()} key={index} position={index}>
        <IndexTable.Cell>
          <Text variant="bodyMd" fontWeight="bold" as="span">{startIndex + index + 1}</Text>
        </IndexTable.Cell>
        {columnNames?.map((col: string, idx: number) => (
          <IndexTable.Cell key={idx}>
            <div style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {row[col] !== null && row[col] !== undefined ? String(row[col]) : <Text tone="subdued" as="span">-</Text>}
            </div>
          </IndexTable.Cell>
        ))}
      </IndexTable.Row>
    ),
  );

  return (
    <AppProvider i18n={enTranslations}>
      <Page
        title="AI Content Generator"
        subtitle="Upload CSV and generate content for Shopify"
        primaryAction={
          hasData ? {
            content: isUploading ? 'Processing...' : 'Process & Push to Shopify',
            onAction: handlePushToShopify,
            loading: isUploading,
            disabled: isUploading || isProcessing
          } : undefined
        }
      >
        <BlockStack gap="500">

          {/* Error Banner */}
          {actionData?.status === "error" && (
            <Banner tone="critical" title="An error occurred">
              <p>{actionData.message}</p>
            </Banner>
          )}

          {/* Upload Section */}
          <Layout>
            <Layout.Section>
              <LegacyCard sectioned>
                <BlockStack gap="400">
                  <DropZone onDrop={handleDrop} allowMultiple={false} accept=".csv" type="file" variableHeight>
                    {file ? (
                      <DropZone.FileUpload actionTitle="Change file" />
                    ) : (
                      <DropZone.FileUpload actionTitle="Upload CSV" />
                    )}
                  </DropZone>

                  {file && (
                    <InlineStack align="space-between" blockAlign="center">
                      <InlineStack gap="200" blockAlign="center">
                        <Thumbnail size="small" alt={file.name} source={NoteIcon} />
                        <BlockStack gap="050">
                          <Text variant="bodyMd" fontWeight="bold" as="span">{file.name}</Text>
                          <Text variant="bodySm" tone="subdued" as="span">{(file.size / 1024).toFixed(1)} KB</Text>
                        </BlockStack>
                      </InlineStack>
                      <Button variant="primary" onClick={handleUpload} loading={isUploading} icon={UploadIcon}>
                        Upload & Analyze
                      </Button>
                    </InlineStack>
                  )}
                </BlockStack>
              </LegacyCard>
            </Layout.Section>
          </Layout>

          {/* File Info & Stats (Only if data loaded) */}
          {hasData && (
            <Layout>
              <Layout.Section>
                <CalloutCard
                  title={`File Analyzed: ${csvData?.file_name}`}
                  illustration="https://cdn.shopify.com/s/assets/admin/checkout/settings-customizecart-705f57c725ac05be5a34ec2edc1ff5d4.svg"
                  primaryAction={{
                    content: 'Process & Push to Shopify',
                    onAction: handlePushToShopify,
                  }}
                >
                  <p>Found <b>{allProducts.length}</b> records ready for processing.</p>
                </CalloutCard>
              </Layout.Section>
            </Layout>
          )}

          {/* Logs Section */}
          {(isProcessing || pushData?.status === "success" || logs.length > 0) && (
            <Layout>
              <Layout.Section>
                <LegacyCard title="System Logs" actions={[{ content: 'Clear', onAction: () => setLogs([]) }]}>
                  <LegacyCard.Section>
                    <InlineStack gap="200" align="start" blockAlign="center">
                      <Badge tone={isConnected ? 'success' : 'critical'}>
                        {isConnected ? 'Live Connection' : 'Disconnected'}
                      </Badge>
                    </InlineStack>
                  </LegacyCard.Section>
                  <Box background="bg-surface-secondary" padding="400" minHeight="200px">
                    <Scrollable shadow style={{ height: '300px' }}>
                      <div style={{ padding: '10px' }}>
                        {logs.length === 0 && <Text tone="subdued" as="p" alignment="center">Waiting for logs...</Text>}
                        {logs.map((log, i) => {
                          const isError = (log.includes("Error") || log.includes("Failed") || log.includes("❌")) && !log.includes("Failed: 0");
                          const isSuccess = log.includes("Success") || log.includes("✅");
                          const isInfo = log.includes("Starting") || log.includes("completed");

                          let color = '#202223';
                          let bg = 'transparent';
                          if (isError) { color = '#7a0b0b'; bg = '#fff4f4'; }
                          else if (isSuccess) { color = '#005c31'; bg = '#f1f8f5'; }
                          else if (isInfo) { color = '#004299'; bg = '#f6faff'; }

                          return (
                            <div key={i} style={{
                              marginBottom: '6px',
                              padding: '6px 10px',
                              borderRadius: '4px',
                              background: bg,
                              color: color,
                              fontFamily: 'monospace',
                              fontSize: '12px',
                              borderLeft: `3px solid ${isError ? '#d72c0d' : isSuccess ? '#00a47c' : isInfo ? '#005bd3' : 'transparent'}`
                            }}>
                              {log}
                            </div>
                          )
                        })}
                        <div ref={logContainerRef} />
                      </div>
                    </Scrollable>
                  </Box>
                </LegacyCard>
              </Layout.Section>
            </Layout>
          )}

          {/* Data Table Section */}
          {hasData && columnNames && (
            <Layout>
              <Layout.Section>
                <LegacyCard>
                  <IndexTable
                    resourceName={resourceName}
                    itemCount={allProducts.length}
                    selectedItemsCount={'All' as any}
                    headings={[
                      { title: '#' },
                      ...columnNames.map((c: string) => ({ title: c }))
                    ]}
                    selectable={false}
                  >
                    {rowMarkup}
                  </IndexTable>

                  <div style={{ display: 'flex', justifyContent: 'center', padding: '16px' }}>
                    <Pagination
                      hasPrevious={currentPage > 1}
                      onPrevious={() => setCurrentPage(p => p - 1)}
                      hasNext={currentPage < totalPages}
                      onNext={() => setCurrentPage(p => p + 1)}
                      label={`Page ${currentPage} of ${totalPages}`}
                    />
                  </div>
                </LegacyCard>
              </Layout.Section>
            </Layout>
          )}

        </BlockStack>
      </Page>
    </AppProvider>
  );
}
