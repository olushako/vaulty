import { useEffect, useState } from 'react';
import { projectApi, secretApi } from '../lib/api';
import { Plus, Eye, EyeOff, Trash2, Lock } from 'lucide-react';
import type { Project, Secret, SecretCreate } from '../types';
import { useToastContext } from '../contexts/ToastContext';
import { extractErrorMessage, logError } from '../lib/utils/errorHandler';
import { formatDateTime } from '../lib/utils/dateFormat';
import { EmptyState } from '../components/EmptyState';
import { LoadingSpinner } from '../components/LoadingSpinner';

const Secrets = () => {
  const toast = useToastContext();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState<SecretCreate>({ key: '', value: '' });
  const [revealed, setRevealed] = useState<Map<string, string>>(new Map());

  const loadProjects = () => {
    projectApi.list()
      .then(setProjects)
      .catch((error) => logError(error, 'Secrets: Load projects'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    if (selectedProject) {
      loadSecrets();
    }
  }, [selectedProject]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadProjects();
      if (selectedProject) {
        loadSecrets();
      }
    }, 60000);
    
    return () => clearInterval(interval);
  }, [selectedProject]);

  const loadSecrets = () => {
    if (!selectedProject) return;
    secretApi.list(selectedProject)
      .then(setSecrets)
      .catch((error) => logError(error, 'Secrets: Load secrets'));
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProject) return;
    try {
      await secretApi.create(selectedProject, formData);
      setFormData({ key: '', value: '' });
      setShowCreate(false);
      loadSecrets();
      toast.success('Secret created successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to create secret');
      toast.error(message);
    }
  };

  const handleDelete = async (key: string) => {
    if (!selectedProject) return;
    if (!confirm(`Are you sure you want to delete secret "${key}"?`)) return;
    try {
      await secretApi.delete(selectedProject, key);
      loadSecrets();
      toast.success('Secret deleted successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to delete secret');
      toast.error(message);
    }
  };

  const toggleReveal = async (key: string) => {
    if (!selectedProject) return;
    if (revealed.has(key)) {
      const newRevealed = new Map(revealed);
      newRevealed.delete(key);
      setRevealed(newRevealed);
    } else {
      try {
        const secret = await secretApi.get(selectedProject, key);
        setRevealed(new Map(revealed).set(key, secret.value));
      } catch (error) {
        const message = extractErrorMessage(error, 'Failed to retrieve secret');
        toast.error(message);
      }
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Secrets</h1>
        {selectedProject && (
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="btn btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Secret
          </button>
        )}
      </div>

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
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Create New Secret</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Key
              </label>
              <input
                type="text"
                required
                className="input"
                value={formData.key}
                onChange={(e) => setFormData({ ...formData, key: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Value
              </label>
              <textarea
                className="input"
                rows={3}
                required
                value={formData.value}
                onChange={(e) => setFormData({ ...formData, value: e.target.value })}
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
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Secrets</h2>
          {secrets.length === 0 ? (
            <EmptyState
              icon={Lock}
              title="No secrets yet"
              description="Add your first secret to get started"
            />
          ) : (
            <div className="space-y-3">
              {secrets.map((secret) => (
                <div key={secret.key} className="p-4 min-h-[60px] bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex-1">
                      <div className="font-medium text-gray-900 dark:text-gray-100">{secret.key}</div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">
                        Updated {formatDateTime(secret.updated_at)}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => toggleReveal(secret.key)}
                        className="p-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:text-gray-100"
                      >
                        {revealed.has(secret.key) ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </button>
                      <button
                        onClick={() => handleDelete(secret.key)}
                        className="p-2 text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  {revealed.has(secret.key) && (
                    <div className="mt-3 p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded">
                      <code className="text-sm text-gray-900 dark:text-gray-100 break-all">
                        {revealed.get(secret.key)}
                      </code>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <EmptyState
          icon={Lock}
          title="No project selected"
          description="Please select a project to view secrets"
        />
      )}
    </div>
  );
};

export default Secrets;

