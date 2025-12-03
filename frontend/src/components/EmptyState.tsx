import { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const EmptyState = ({ icon: Icon, title, description, action }: EmptyStateProps) => {
  return (
    <div className="card p-12 text-center">
      <Icon className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
      <p className="text-gray-500 dark:text-gray-400 mb-2">{title}</p>
      {description && <p className="text-sm text-gray-400 dark:text-gray-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
};

