import { Search } from 'lucide-react';
import ThemeToggle from './ThemeToggle';

const Header = () => {
  return (
    <div className="bg-white dark:bg-[#161b22] border-b border-gray-200 dark:border-[#30363d] header-padding sticky top-0 z-10 h-[73px] flex items-center">
      <div className="flex items-center justify-between max-w-7xl mx-auto w-full">
        <div className="flex-1 max-w-md">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400 dark:text-[#6e7681]" />
            <input
              type="text"
              placeholder="Search..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-[#30363d] rounded-lg bg-white dark:bg-[#0d1117] text-gray-900 dark:text-[#c9d1d9] placeholder-gray-400 dark:placeholder-[#6e7681] focus:outline-none focus:ring-2 focus:ring-primary-500 dark:focus:ring-primary-400 focus:border-transparent"
            />
          </div>
        </div>
        <ThemeToggle />
      </div>
    </div>
  );
};

export default Header;

