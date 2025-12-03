import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './lib/theme';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Dashboard from './pages/Dashboard';
import Projects from './pages/Projects';
import ProjectView from './pages/ProjectView';
import Secrets from './pages/Secrets';
import Tokens from './pages/Tokens';
import Settings from './pages/Settings';
import Auth from './pages/Auth';
import InitialTokenWarning from './components/InitialTokenWarning';
import { getAuthToken } from './lib/api';
import { ToastProvider } from './contexts/ToastContext';
import { TOKEN_CHECK_INTERVAL_MS } from './lib/utils/constants';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = getAuthToken();
  if (!token) {
    return <Navigate to="/auth" replace />;
  }
  return <>{children}</>;
};

function App() {
  const [token, setToken] = useState<string | null>(getAuthToken());

  useEffect(() => {
    // Listen for storage changes (when token is set in another tab/window)
    const handleStorageChange = () => {
      setToken(getAuthToken());
    };
    window.addEventListener('storage', handleStorageChange);
    
    // Check token expiration periodically
    const interval = setInterval(() => {
      const currentToken = getAuthToken();
      if (currentToken !== token) {
        setToken(currentToken);
      }
    }, TOKEN_CHECK_INTERVAL_MS);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      clearInterval(interval);
    };
  }, [token]);

  return (
    <ThemeProvider>
      <ToastProvider>
        <BrowserRouter>
          {!token ? (
            <Routes>
              <Route path="/auth" element={<Auth />} />
              <Route path="*" element={<Navigate to="/auth" replace />} />
            </Routes>
          ) : (
            <>
              <InitialTokenWarning />
              <div className="flex h-screen bg-gray-50 dark:bg-[#0d1117]">
                <Sidebar />
                <div className="flex-1 flex flex-col ml-64 overflow-hidden">
                  <Header />
                  <main className="flex-1 overflow-y-auto bg-gray-50 dark:bg-[#0d1117]">
                    <Routes>
                      <Route
                        path="/"
                        element={
                          <ProtectedRoute>
                            <Dashboard />
                          </ProtectedRoute>
                        }
                      />
                      <Route
                        path="/projects"
                        element={
                          <ProtectedRoute>
                            <Projects />
                          </ProtectedRoute>
                        }
                      />
                      <Route
                        path="/projects/:id"
                        element={
                          <ProtectedRoute>
                            <ProjectView />
                          </ProtectedRoute>
                        }
                      />
                      <Route
                        path="/secrets"
                        element={
                          <ProtectedRoute>
                            <Secrets />
                          </ProtectedRoute>
                        }
                      />
                      <Route
                        path="/tokens"
                        element={
                          <ProtectedRoute>
                            <Tokens />
                          </ProtectedRoute>
                        }
                      />
                      <Route
                        path="/master-tokens"
                        element={<Navigate to="/settings?tab=master-tokens" replace />}
                      />
                      <Route
                        path="/settings"
                        element={
                          <ProtectedRoute>
                            <Settings />
                          </ProtectedRoute>
                        }
                      />
                      <Route 
                        path="/auth" 
                        element={token ? <Navigate to="/" replace /> : <Auth />} 
                      />
                      <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
                  </main>
                </div>
              </div>
            </>
          )}
        </BrowserRouter>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default App;



