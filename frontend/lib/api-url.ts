const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

/**
 * Mantém cookies CSRF/refresh no mesmo site quando a demo é aberta por
 * localhost ou 127.0.0.1. Em produção, a URL configurada permanece intacta.
 */
export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!configured) throw new Error("API_BASE_URL não configurada.");

  const apiUrl = new URL(configured);
  if (typeof window === "undefined") {
    return apiUrl.toString().replace(/\/$/, "");
  }

  const pageUrl = new URL(window.location.href);
  if (LOCAL_HOSTS.has(pageUrl.hostname) && LOCAL_HOSTS.has(apiUrl.hostname)) {
    apiUrl.protocol = pageUrl.protocol;
    apiUrl.hostname = pageUrl.hostname;
  }

  return apiUrl.toString().replace(/\/$/, "");
}
