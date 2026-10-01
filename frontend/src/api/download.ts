import { apiClient } from "./client";

/** Downloads an authenticated endpoint's response as a file (Authorization
 * header is required, so a plain <a href> won't work for these). */
export async function downloadAuthenticated(url: string, suggestedFilename: string) {
  const response = await apiClient.get(url, { responseType: "blob" });
  const disposition: string | undefined = response.headers["content-disposition"];
  let filename = suggestedFilename;
  const match = disposition?.match(/filename=([^;]+)/);
  if (match) filename = match[1].trim().replace(/"/g, "");

  const blobUrl = window.URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(blobUrl);
}
