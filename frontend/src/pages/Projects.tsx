import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { projectApi } from '../lib/api';
import { Plus, Trash2, Folder, Calendar, ArrowRight } from 'lucide-react';
import type { Project, ProjectCreate } from '../types';
import { useToastContext } from '../contexts/ToastContext';
import { extractErrorMessage, logError } from '../lib/utils/errorHandler';
import { formatDate } from '../lib/utils/dateFormat';
import { EmptyState } from '../components/EmptyState';
import { LoadingSpinner } from '../components/LoadingSpinner';

const Projects = () => {
  const navigate = useNavigate();
  const toast = useToastContext();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState<ProjectCreate>({ name: '', description: '' });

  useEffect(() => {
    // Load projects immediately
    loadProjects();
    
    // Set up auto-refresh every 60 seconds
    const interval = setInterval(() => {
      loadProjects();
    }, 60000);
    
    // Cleanup interval on unmount
    return () => clearInterval(interval);
  }, []);

  const loadProjects = () => {
    setLoading(true);
    projectApi.list()
      .then(setProjects)
      .catch((error) => logError(error, 'Projects: Load'))
      .finally(() => setLoading(false));
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await projectApi.create(formData);
      setFormData({ name: '', description: '' });
      setShowCreate(false);
      loadProjects();
      toast.success('Project created successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to create project');
      toast.error(message);
    }
  };

  const handleDelete = async (projectName: string) => {
    if (!confirm('Are you sure you want to delete this project?')) return;
    try {
      await projectApi.delete(projectName);
      loadProjects();
      toast.success('Project deleted successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to delete project');
      toast.error(message);
    }
  };


  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Projects</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="btn btn-primary flex items-center gap-2 text-sm py-1.5 px-3"
        >
          <Plus className="w-3.5 h-3.5" />
          Create Project
        </button>
      </div>

      {showCreate && (
        <div className="card p-6 mb-6">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Create New Project</h2>
          <form onSubmit={handleCreate} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                Project Name
              </label>
              <input
                type="text"
                required
                className="input text-sm py-1.5"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                Description
              </label>
              <textarea
                className="input text-sm py-1.5"
                rows={2}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
            <div className="flex gap-2">
              <button type="submit" className="btn btn-primary text-sm py-1.5 px-3">
                Create
              </button>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="btn btn-secondary text-sm py-1.5 px-3"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {projects.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {projects.map((project) => (
            <div
              key={project.id}
              className="group relative bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-primary-300 dark:hover:border-primary-600 shadow-sm hover:shadow-md transition-all duration-200 cursor-pointer overflow-hidden"
              onClick={(e) => {
                e.preventDefault();
                const target = `/projects/${encodeURIComponent(project.name)}`;
                console.log('Navigating to:', target);
                navigate(target);
              }}
            >
              {/* Gradient accent bar */}
              <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-primary-500 via-primary-400 to-primary-600"></div>
              
              <div className="p-3">
                {/* Header with icon and actions */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <div className="p-1.5 bg-primary-100 dark:bg-primary-900/30 rounded-md group-hover:bg-primary-200 dark:group-hover:bg-primary-900/50 transition-colors flex-shrink-0">
                      <Folder className="w-4 h-4 text-primary-600 dark:text-primary-400" />
                    </div>
                    <h3 className="font-semibold text-sm text-gray-900 dark:text-gray-100 truncate group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors">
                      {project.name}
                    </h3>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(project.name);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-all flex-shrink-0"
                    title="Delete project"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Description */}
                {project.description ? (
                  <p className="text-xs text-gray-600 dark:text-gray-300 mb-2 overflow-hidden" style={{
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                  }}>
                    {project.description}
                  </p>
                ) : (
                  <p className="text-xs text-gray-400 dark:text-gray-500 italic mb-2">
                    No description
                  </p>
                )}

                {/* Footer with date and arrow */}
                <div className="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-gray-700">
                  <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                    <Calendar className="w-3 h-3" />
                    <span>{formatDate(project.created_at)}</span>
                  </div>
                  <div className="flex items-center gap-1 text-primary-600 dark:text-primary-400 opacity-0 group-hover:opacity-100 transition-opacity">
                    <span className="text-xs font-medium">View</span>
                    <ArrowRight className="w-3 h-3" />
                  </div>
                </div>
              </div>

              {/* Hover overlay effect */}
              <div className="absolute inset-0 bg-primary-50 dark:bg-primary-900/10 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"></div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Folder}
          title="No projects yet"
          description="Create your first project to get started"
        />
      )}

    </div>
  );
};

export default Projects;

