import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface DailyStat {
  date: string;
  day: string;
  total: number;
  [key: string]: any; // Allow dynamic project name keys
}

interface ActivityChartProps {
  data: DailyStat[];
  categories: string[];
  avgResponseTime?: number | null;
  isStacked?: boolean;
}

// Professional color palette for data visualization
// Based on ColorBrewer and D3 color scales best practices
const getProjectColor = (index: number, totalProjects: number) => {
  // Use a carefully curated palette that's:
  // 1. Perceptually uniform
  // 2. Colorblind-friendly
  // 3. Works in both light and dark modes
  // 4. Provides good contrast for stacked bars
  
  // Extended palette with smooth transitions (inspired by D3 category20 and ColorBrewer)
  const professionalPalette = [
    '#3b82f6', // Blue - primary
    '#8b5cf6', // Purple
    '#10b981', // Green
    '#f59e0b', // Amber
    '#ef4444', // Red
    '#06b6d4', // Cyan
    '#ec4899', // Pink
    '#84cc16', // Lime
    '#6366f1', // Indigo
    '#14b8a6', // Teal
    '#f97316', // Orange
    '#a855f7', // Violet
    '#22c55e', // Emerald
    '#eab308', // Yellow
    '#06b6d4', // Sky
    '#f43f5e', // Rose
  ];
  
  // If we have more categories than palette colors, generate smooth transitions
  if (index < professionalPalette.length) {
    return professionalPalette[index];
  }
  
  // For additional colors, use a perceptually uniform color scale
  // Using LAB color space approximation for better perceptual uniformity
  const extendedIndex = index - professionalPalette.length;
  const totalExtended = totalProjects - professionalPalette.length;
  
  // Create smooth gradient using HSL with optimized parameters
  // Use a narrower hue range (200-360) for better visual harmony
  const hueStart = 200; // Start from cyan-blue
  const hueEnd = 360; // End at red (wraps to 0)
  const hueRange = hueEnd - hueStart;
  const hue = hueStart + (extendedIndex * hueRange) / Math.max(totalExtended, 1);
  
  // Use consistent, optimized saturation and lightness
  // These values are tested for good visibility in both light and dark modes
  const saturation = 65;
  const lightness = 50;
  
  return `hsl(${hue % 360}, ${saturation}%, ${lightness}%)`;
};

export const ActivityChart = ({ data, categories, avgResponseTime, isStacked = false }: ActivityChartProps) => {
  // Handle empty data
  if (!data || data.length === 0) {
    return (
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            Events (Last 7 Days)
          </h3>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            No data
          </div>
        </div>
        <div className="flex items-center justify-center h-80 text-gray-400 dark:text-gray-500">
          No activity data available
        </div>
      </div>
    );
  }

  const maxValue = Math.max(...data.map(d => d.total), 1);
  const totalEvents = data.reduce((sum, d) => sum + d.total, 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs text-gray-500 dark:text-gray-400">
          {avgResponseTime !== null && avgResponseTime !== undefined && (
            <span>Avg Response Time: <span className="font-semibold text-gray-700 dark:text-gray-300">{avgResponseTime}ms</span></span>
          )}
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400">
          Total Events: <span className="font-semibold text-gray-700 dark:text-gray-300">{totalEvents.toLocaleString()}</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart 
          data={data} 
          margin={{ top: 15, right: 15, left: 0, bottom: 10 }}
          barCategoryGap="15%"
        >
          <CartesianGrid 
            strokeDasharray="3 3" 
            stroke="#e5e7eb" 
            className="dark:stroke-gray-700"
            vertical={false}
          />
          <XAxis 
            dataKey="day" 
            tick={{ fill: '#6b7280', fontSize: 12, fontWeight: 500 }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickLine={false}
            className="dark:text-gray-400"
          />
          <YAxis 
            tick={{ fill: '#6b7280', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={45}
            className="dark:text-gray-400"
          />
          <Tooltip 
            content={({ active, payload, label }) => {
              if (!active || !payload || !payload.length) {
                return null;
              }
              
              // Sort payload by value (largest to smallest)
              const sortedPayload = [...payload].sort((a: any, b: any) => {
                const valueA = a.value || 0;
                const valueB = b.value || 0;
                return valueB - valueA;
              });
              
              return (
                <div
                  className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-xs shadow-lg p-2"
                >
                  <p className="text-gray-900 dark:text-gray-100 font-semibold mb-1.5 text-sm">
                    {label}
                  </p>
                  {sortedPayload.map((entry: any, index: number) => {
                    const value = entry.value || 0;
                    const name = isStacked && categories.includes(entry.name) 
                      ? entry.name 
                      : (entry.name === 'total' ? 'Events' : entry.name);
                    
                    return (
                      <div
                        key={index}
                        className="text-gray-900 dark:text-gray-200 py-1 flex items-center gap-2"
                      >
                        <span 
                          className="inline-block w-3 h-3 rounded-sm flex-shrink-0"
                          style={{ 
                            backgroundColor: entry.color
                          }}
                        />
                        <span className="text-xs">{name}: </span>
                        <span className="font-bold text-sm text-gray-900 dark:text-gray-50">
                          {value.toLocaleString()}
                        </span>
                      </div>
                    );
                  })}
                </div>
              );
            }}
            cursor={{ fill: 'rgba(59, 130, 246, 0.08)' }}
          />
          {isStacked && categories.length > 0 ? (
            // Stacked bars by path
            categories.map((path, index) => (
              <Bar
                key={path}
                dataKey={path}
                name={path}
                stackId="paths"
                fill={getProjectColor(index, categories.length)}
                radius={index === categories.length - 1 ? [8, 8, 0, 0] : [0, 0, 0, 0]}
              />
            ))
          ) : (
            // Single bar for total
            <Bar
              dataKey="total"
              name="Events"
              fill="#3b82f6"
              radius={[8, 8, 0, 0]}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
