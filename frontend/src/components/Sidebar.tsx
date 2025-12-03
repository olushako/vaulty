import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Home, Lock, Folder, Settings, LogOut, Cog, Trash2, Plus, Edit2, X } from 'lucide-react';
import { useState, useEffect } from 'react';
import { authApi, logout, activityApi, projectApi } from '../lib/api';
import type { AuthInfo } from '../lib/api';
import type { Project, ProjectCreate } from '../types';
import { REFRESH_INTERVAL_MS } from '../lib/utils/constants';
import { logError, extractErrorMessage } from '../lib/utils/errorHandler';
import { useToastContext } from '../contexts/ToastContext';

const Sidebar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [authInfo, setAuthInfo] = useState<AuthInfo | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsExpanded, setProjectsExpanded] = useState<boolean>(true);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [showCreateProject, setShowCreateProject] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [projectFormData, setProjectFormData] = useState<ProjectCreate>({ name: '', description: '' });
  const toast = useToastContext();

  useEffect(() => {
    // Fetch current auth info to get token name
    authApi.getCurrentAuth()
      .then((info) => {
        setAuthInfo(info);
      })
      .catch((error) => {
        // If it fails, token might be invalid
        console.error('Failed to fetch auth info:', error);
        setAuthInfo(null);
      });
  }, []);

  useEffect(() => {
    // Load projects
    loadProjects();
    
    // Set up auto-refresh every 60 seconds
    const interval = setInterval(() => {
      loadProjects();
    }, REFRESH_INTERVAL_MS);
    
    return () => clearInterval(interval);
  }, []);

  const loadProjects = () => {
    setProjectsLoading(true);
    projectApi.list()
      .then(setProjects)
      .catch((error) => {
        logError(error, 'Sidebar: Load projects');
        setProjects([]);
      })
      .finally(() => setProjectsLoading(false));
  };

  // Check if current route is a project view
  const isProjectView = location.pathname.startsWith('/projects/');
  const currentProjectName = isProjectView ? decodeURIComponent(location.pathname.split('/projects/')[1]?.split('?')[0] || '') : null;

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!authInfo?.is_master) {
      toast.error('Only master tokens can create projects');
      return;
    }
    try {
      await projectApi.create(projectFormData);
      setProjectFormData({ name: '', description: '' });
      setShowCreateProject(false);
      loadProjects();
      toast.success('Project created successfully');
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to create project');
      toast.error(message);
    }
  };

  const handleEditProject = (project: Project) => {
    setEditingProject(project);
    setProjectFormData({ name: project.name, description: project.description || '' });
    setShowCreateProject(true);
  };

  const handleUpdateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingProject || !authInfo?.is_master) {
      toast.error('Only master tokens can edit projects');
      return;
    }
    try {
      // Note: Currently API only supports updating auto_approval_tag_pattern
      // For now, we'll show a message that name/description editing isn't supported
      toast.error('Project name and description editing is not yet supported via API');
      setEditingProject(null);
      setShowCreateProject(false);
      setProjectFormData({ name: '', description: '' });
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to update project');
      toast.error(message);
    }
  };

  const handleDeleteProject = async (projectName: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!authInfo?.is_master) {
      toast.error('Only master tokens can delete projects');
      return;
    }
    if (!confirm(`Are you sure you want to delete project "${projectName}"? This will delete all secrets, tokens, and devices in this project.`)) {
      return;
    }
    try {
      await projectApi.delete(projectName);
      loadProjects();
      toast.success('Project deleted successfully');
      // If we're viewing the deleted project, navigate away
      if (currentProjectName === projectName) {
        navigate('/');
      }
    } catch (error) {
      const message = extractErrorMessage(error, 'Failed to delete project');
      toast.error(message);
    }
  };

  const cancelProjectForm = () => {
    setShowCreateProject(false);
    setEditingProject(null);
    setProjectFormData({ name: '', description: '' });
  };


  const navItems = [
    { path: '/', icon: Home, label: 'Dashboard' },
  ];

  return (
    <div className="w-64 bg-white dark:bg-[#161b22] border-r border-gray-200 dark:border-[#30363d] h-screen fixed left-0 top-0 flex flex-col">
      <div className="header-padding border-b border-gray-200 dark:border-[#30363d] h-[73px] flex items-center">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center flex-shrink-0">
            <Lock className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-semibold text-gray-900 dark:text-[#c9d1d9] leading-tight">Vaulty</h1>
            <p className="text-xs text-gray-500 dark:text-[#8b949e] leading-tight">Secrets Manager</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {/* Dashboard */}
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`sidebar-link ${isActive ? 'active' : ''}`}
            >
              <Icon className="w-5 h-5" />
              <span className="flex-1">{item.label}</span>
            </Link>
          );
        })}

        {/* Projects Tree */}
        <div className="mt-1">
          <button
            onClick={() => setProjectsExpanded(!projectsExpanded)}
            className={`sidebar-link w-full ${
              isProjectView ? 'active' : ''
            }`}
          >
            <Folder className="w-5 h-5" />
            <span className="flex-1 text-left">Projects</span>
            {authInfo?.is_master && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setEditingProject(null);
                  setProjectFormData({ name: '', description: '' });
                  setShowCreateProject(true);
                }}
                className="p-1 text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 hover:bg-white/10 dark:hover:bg-black/10 rounded transition-colors -mr-1"
                title="Create new project"
              >
                <Plus className="w-4 h-4" />
              </button>
            )}
          </button>

          {projectsExpanded && (
            <div className="ml-4 mt-1 space-y-0.5">

              {projectsLoading ? (
                <div className="px-3 py-2 text-xs text-gray-500 dark:text-[#8b949e]">Loading...</div>
              ) : projects.length === 0 && !showCreateProject ? (
                <div className="px-3 py-2 text-xs text-gray-400 dark:text-[#6e7681] italic">No projects</div>
              ) : (
                projects.map((project) => {
                  const projectPath = `/projects/${encodeURIComponent(project.name)}`;
                  const isActive = currentProjectName === project.name;
                  
                  return (
                    <div
                      key={project.id}
                      className={`group flex items-center gap-1 px-2 py-1 rounded-md transition-colors ${
                        isActive
                          ? 'bg-primary-100 dark:bg-[#1f2328]'
                          : 'hover:bg-gray-100 dark:hover:bg-[#161b22]'
                      }`}
                    >
                      <Link
                        to={projectPath}
                        className={`flex-1 flex items-center gap-2 py-1 text-xs transition-colors ${
                          isActive
                            ? 'text-primary-700 dark:text-[#c9d1d9] font-medium'
                            : 'text-gray-600 dark:text-[#8b949e] hover:text-gray-900 dark:hover:text-[#c9d1d9]'
                        }`}
                        title={project.description || project.name}
                      >
                        <div className="w-1.5 h-1.5 rounded-full bg-current opacity-60 flex-shrink-0"></div>
                        <span className="truncate">{project.name}</span>
                      </Link>
                      {authInfo?.is_master && (
                        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              handleEditProject(project);
                            }}
                            className="p-1 text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 rounded transition-colors"
                            title="Edit project"
                          >
                            <Edit2 className="w-3 h-3" />
                          </button>
                          <button
                            onClick={(e) => handleDeleteProject(project.name, e)}
                            className="p-1 text-gray-500 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400 rounded transition-colors"
                            title="Delete project"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* Create/Edit Project Form */}
          {showCreateProject && authInfo?.is_master && (
            <div className="ml-4 mt-2 p-3 bg-gray-50 dark:bg-[#0d1117] rounded-lg border border-gray-200 dark:border-[#30363d]">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-semibold text-gray-900 dark:text-[#c9d1d9]">
                  {editingProject ? 'Edit Project' : 'Create Project'}
                </h3>
                <button
                  onClick={cancelProjectForm}
                  className="p-0.5 text-gray-400 hover:text-gray-600 dark:hover:text-[#c9d1d9] rounded"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
              <form onSubmit={editingProject ? handleUpdateProject : handleCreateProject} className="space-y-2">
                <div>
                  <input
                    type="text"
                    required
                    disabled={!!editingProject}
                    placeholder="Project name"
                    className="input text-xs py-1.5 w-full"
                    value={projectFormData.name}
                    onChange={(e) => setProjectFormData({ ...projectFormData, name: e.target.value })}
                  />
                </div>
                <div>
                  <textarea
                    placeholder="Description (optional)"
                    rows={2}
                    className="input text-xs py-1.5 w-full"
                    value={projectFormData.description}
                    onChange={(e) => setProjectFormData({ ...projectFormData, description: e.target.value })}
                  />
                </div>
                <div className="flex gap-1">
                  <button
                    type="submit"
                    className="flex-1 btn btn-primary text-xs py-1 px-2"
                  >
                    {editingProject ? 'Update' : 'Create'}
                  </button>
                  <button
                    type="button"
                    onClick={cancelProjectForm}
                    className="btn btn-secondary text-xs py-1 px-2"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>

        {/* Settings */}
        <div className="mt-1">
          <Link
            to="/settings"
            className={`sidebar-link ${location.pathname === '/settings' ? 'active' : ''}`}
          >
            <Cog className="w-5 h-5" />
            <span className="flex-1 text-left">Settings</span>
          </Link>
        </div>
        
        {/* Temporary: Flush All Activities Button */}
        {authInfo?.is_master && (
          <button
            onClick={async () => {
              if (window.confirm('Are you sure you want to flush ALL activities? This cannot be undone.')) {
                try {
                  const result = await activityApi.flushAll();
                  toast.success(`Flushed ${result.deleted} activities`);
                  // Reload the page to refresh activity lists
                  window.location.reload();
                } catch (error) {
                  logError(error, 'Sidebar: Flush all activities');
                  toast.error('Failed to flush activities');
                }
              }
            }}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors mt-2 border border-red-200 dark:border-red-800/50"
            title="Temporary: Flush all activities (Master token only)"
          >
            <Trash2 className="w-4 h-4" />
            <span>Flush All Activities</span>
          </button>
        )}
      </nav>

      <div className="p-4 border-t border-gray-200 dark:border-[#30363d]">
        <div className="text-xs text-gray-500 dark:text-[#8b949e] px-3 mb-3">
          {authInfo ? (
            <>
              <div className="font-medium text-gray-700 dark:text-[#c9d1d9]">
                {authInfo.is_master ? 'Master Token' : 'Project Token'}
              </div>
              <div className="truncate" title={authInfo.token_name}>
                {authInfo.token_name}
              </div>
            </>
          ) : (
            <div className="text-gray-400 dark:text-[#6e7681]">Loading...</div>
          )}
        </div>
        <button
          onClick={logout}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-[#c9d1d9] hover:bg-gray-100 dark:hover:bg-[#161b22] rounded-lg transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span>Logout</span>
        </button>
      </div>
    </div>
  );
};

export default Sidebar;


