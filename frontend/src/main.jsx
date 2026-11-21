function installCsrfAwareFetch() {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const requestObject = typeof Request !== "undefined" && input instanceof Request
      ? input
      : null;
    const resource = typeof input === "string" || input instanceof URL
      ? input.toString()
      : input.url;
    const target = new URL(resource, window.location.href);
    const method = String(init.method || requestObject?.method || "GET").toUpperCase();
    const isMutation = ["POST", "PUT", "PATCH", "DELETE"].includes(method);
    const isApplicationApi = target.pathname.startsWith("/api/") || target.pathname === "/predict";

    if (isMutation && isApplicationApi && target.origin === window.location.origin) {
      const cookiePrefix = "mannkidhun_csrf=";
      const csrfCookie = document.cookie
        .split(";")
        .map((part) => part.trim())
        .find((part) => part.startsWith(cookiePrefix));
      if (csrfCookie) {
        const token = decodeURIComponent(csrfCookie.slice(cookiePrefix.length));
        const headers = new Headers(requestObject?.headers);
        new Headers(init.headers).forEach((value, key) => headers.set(key, value));
        headers.set("X-CSRF-Token", token);
        init = { ...init, headers };
      }
    }

    return nativeFetch(input, init);
  };
}

installCsrfAwareFetch();

import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles/global.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
