import axios from "axios";

let accessToken: string | null = sessionStorage.getItem("access_token");
let onUnauthorized: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
  if (token) {
    sessionStorage.setItem("access_token", token);
  } else {
    sessionStorage.removeItem("access_token");
  }
}

export function getAccessToken() {
  return accessToken;
}

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

export const apiClient = axios.create({
  baseURL: "/api/v1",
});

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && onUnauthorized) {
      onUnauthorized();
    }
    return Promise.reject(error);
  }
);

export interface ApiErrorBody {
  detail: string;
  code: string;
}

export function errorMessage(err: unknown): string {
  const anyErr = err as any;
  const body: ApiErrorBody | undefined = anyErr?.response?.data;
  if (body?.detail) return body.detail;
  return "Something went wrong. Please try again.";
}
