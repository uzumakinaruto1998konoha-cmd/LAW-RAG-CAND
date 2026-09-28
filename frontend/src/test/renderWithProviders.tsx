import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, RenderResult } from "@testing-library/react";
import { ToastProvider } from "../shared/ui";

/** Query client for tests: no retries, no cache reuse between cases. */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
}

interface RenderOptions {
  /** Initial history entry (also used to resolve `useParams` when `path` is given). */
  route?: string;
  /** Route pattern to mount `ui` under, e.g. "/documents/:documentId". */
  path?: string;
}

/** Render a screen with the providers the app uses (query client, toasts, router). */
export function renderWithProviders(ui: React.ReactElement, options: RenderOptions = {}): RenderResult {
  const { route = "/", path } = options;
  const content = path ? (
    <Routes>
      <Route path={path} element={ui} />
    </Routes>
  ) : (
    ui
  );

  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <ToastProvider>
        <MemoryRouter initialEntries={[route]}>{content}</MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
