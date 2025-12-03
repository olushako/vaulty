import { Moon, Sun, Monitor } from 'lucide-react';
import { useTheme } from '../lib/theme';

const ThemeToggle = () => {
  const { theme, setTheme } = useTheme();

  const themes: Array<{ value: 'light' | 'dark' | 'system'; icon: React.ReactNode; label: string }> = [
    { value: 'light', icon: <Sun className="w-4 h-4" />, label: 'Light' },
    { value: 'dark', icon: <Moon className="w-4 h-4" />, label: 'Dark' },
    { value: 'system', icon: <Monitor className="w-4 h-4" />, label: 'System' },
  ];

  return (
    <div className="flex items-center gap-1 bg-gray-100 dark:bg-[#21262d] rounded-lg p-1">
      {themes.map((t) => (
        <button
          key={t.value}
          onClick={() => setTheme(t.value)}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors ${
            theme === t.value
              ? 'bg-white dark:bg-[#30363d] text-gray-900 dark:text-[#c9d1d9] shadow-sm'
              : 'text-gray-600 dark:text-[#8b949e] hover:text-gray-900 dark:hover:text-[#c9d1d9]'
          }`}
          title={t.label}
        >
          {t.icon}
        </button>
      ))}
    </div>
  );
};

export default ThemeToggle;




