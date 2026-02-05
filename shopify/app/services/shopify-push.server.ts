export interface ShopifyPushResponse {
  status: string;
  total_products: number;
  success_count: number;
  failed_count: number;
  results: Array<{
    row_index: number;
    status: string;
    product_id?: string;
    shopify_url?: string;
    title?: string;
    message?: string;
  }>;
}

export const pushToShopify = async (): Promise<ShopifyPushResponse> => {
  const backendUrl = process.env.PYTHON_BACKEND_URL;
  // Check for SHOPIFY_STORE_URL (backend convention) or SHOPIFY_SHOP_URL
  const shopUrl = process.env.SHOPIFY_STORE_URL || process.env.SHOPIFY_SHOP_URL;
  const accessToken = process.env.SHOPIFY_ACCESS_TOKEN;

  if (!backendUrl) throw new Error("PYTHON_BACKEND_URL is not set");
  if (!shopUrl) throw new Error("SHOPIFY_STORE_URL (or SHOPIFY_SHOP_URL) is not set in .env");
  if (!accessToken) throw new Error("SHOPIFY_ACCESS_TOKEN is not set in .env");

  try {
    const response = await fetch(`${backendUrl}/push-to-shopify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        shop_url: shopUrl,
        access_token: accessToken,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorData.detail || `Push failed: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error("Failed to push to Shopify:", error);
    throw error;
  }
};
