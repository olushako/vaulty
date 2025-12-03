import { useEffect, useState } from 'react';
import { projectApi, tokenApi } from '../lib/api';
import { Plus, Copy, Trash2, Key } from 'lucide-react';
import type { Project, Token, TokenCreate } from '../types';
import { useToastContext } from '../contexts/ToastContext';
import { useClipboard } from '../hooks/useClipboard';
import { extractErrorMessage, logError } from '../lib/utils/errorHandler';
import { formatDate } from '../lib/utils/dateFormat';
import { EmptyState } from '../components/EmptyState';
import { LoadingSpinner } from '../components/LoadingSpinner';

const Tokens = () => {
  const toast = useToastContext();
  const { copied, copyToClipboard } = useClipboard();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [tokens, setTokens] = useState<Token[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState<TokenCreate>({ name: '' });
  const [newToken, setNewToken] = useState<string | null>(null);

  const loadProjects = () => {
    projectApi.list()
      .then(setProjects)
      .catch((error) => logError(error, 'Tokens: Load projects'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    if (selectedProject) {
      loadTokens();
    }
  }, [selectedProject]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadProjects();
      if (selectedProject) {
        loadTokens();
      }
    }, 60000);
    
    return () => clearInterval(interval);
  }, [selectedProject]);

  const loadTokens = () => {
    if (!selectedProject) return;
    tokenApi.list(selectedProject)
      .then(setTokens)
      .catch((error) => logError(error, 'Tokens: Load tokens'));
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProject) return;
    try {
      const token = await tokenApi.create(selectedProject, formData);
      setNewToken(token.token || null);
      setFormData({ name: '' });
      setShowCreate(false);
      loadTokens();
      toast.success('Token created successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to create token');
      toast.error(message);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to revoke this token?')) return;
    try {
      await tokenApi.revoke(id);
      loadTokens();
      toast.success('Token revoked successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to revoke token');
      toast.error(message);
    }
  };

  const handleCopy = async (text: string) => {
    const success = await copyToClipboard(text);
    if (success) {
      toast.success('Copied to clipboard!');
    } else {
      toast.error('Failed to copy to clipboard');
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Tokens</h1>
        {selectedProject && (
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="btn btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Create Token
          </button>
        )}
      </div>

      {newToken && (
        <div className="card p-6 mb-6 bg-primary-50 dark:bg-primary-900/20 border-primary-200 dark:border-primary-800">
          <h3 className="font-semibold text-primary-900 dark:text-primary-300 mb-2">New Token Created</h3>
          <p className="text-sm text-primary-700 dark:text-primary-400 mb-3">
            Save this token now. You won't be able to see it again!
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 px-3 py-2 bg-white dark:bg-gray-800 border border-primary-200 dark:border-primary-800 rounded text-sm text-gray-900 dark:text-gray-100">
              {newToken}
            </code>
            <button
              onClick={() => handleCopy(newToken)}
              className="btn btn-primary flex items-center gap-2"
            >
              <Copy className="w-4 h-4" />
              {copied ? 'Copied!' : 'Copy'}
            </button>
            <button
              onClick={() => setNewToken(null)}
              className="btn btn-secondary"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Select Project
        </label>
        <select
          className="input"
          value={selectedProject || ''}
          onChange={(e) => setSelectedProject(e.target.value || null)}
        >
          <option value="">-- Select a project --</option>
          {projects.map((project) => (
            <option key={project.id} value={project.name}>
              {project.name}
            </option>
          ))}
        </select>
      </div>

      {showCreate && selectedProject && (
        <div className="card p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Create New Token</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Token Name
              </label>
              <input
                type="text"
                required
                className="input"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            <div className="flex gap-2">
              <button type="submit" className="btn btn-primary">
                Create
              </button>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {selectedProject ? (
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Project Tokens</h2>
          {tokens.length === 0 ? (
            <EmptyState
              icon={Key}
              title="No tokens yet"
              description="Create your first token to get started"
            />
          ) : (
            <div className="space-y-3">
              {tokens.map((token) => (
                <div key={token.id} className="flex items-center justify-between p-4 min-h-[60px] bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div>
                    <div className="font-medium text-gray-900 dark:text-gray-100">{token.name}</div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      Created {formatDate(token.created_at)}
                      {token.last_used && ` • Last used ${formatDate(token.last_used)}`}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(token.id)}
                    className="p-2 text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <EmptyState
          icon={Key}
          title="No project selected"
          description="Please select a project to view tokens"
        />
      )}
    </div>
  );
};

export default Tokens;

