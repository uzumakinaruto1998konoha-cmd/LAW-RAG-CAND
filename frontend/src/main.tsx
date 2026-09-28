import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./features/auth/AuthProvider";
import { ToastProvider } from "./shared/ui";
import { AppShell } from "./shared/layout/AppShell";
import { RequireAuth } from "./features/auth/RequireAuth";
import { DevLogin } from "./features/auth/DevLogin";
import SearchPage from "./pages/SearchPage";
import ChatPage from "./pages/ChatPage";
import ConversationsPage from "./pages/ConversationsPage";
import DocumentListPage from "./pages/DocumentListPage";
import DocumentDetailPage from "./pages/DocumentDetailPage";
import TracePage from "./pages/TracePage";
import AdminPage from "./pages/AdminPage";
import HealthPage from "./pages/HealthPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/dev/login" element={<DevLogin />} />
              <Route path="/health" element={<HealthPage />} />
              <Route
                path="/"
                element={
                  <RequireAuth>
                    <AppShell />
                  </RequireAuth>
                }
              >
                <Route index element={<SearchPage />} />
                <Route path="search" element={<SearchPage />} />
                <Route path="chat" element={<ChatPage />} />
                <Route path="conversations" element={<ConversationsPage />} />
                <Route path="documents" element={<DocumentListPage />} />
                <Route path="documents/:documentId" element={<DocumentDetailPage />} />
                <Route path="traces/:traceId" element={<TracePage />} />
                <Route path="admin" element={<AdminPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}