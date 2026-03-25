import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';

export default function OccupancyChart({ history, capacity }) {
  if (!history || history.length === 0) {
    return (
      <div className="bg-sim-card rounded-lg p-4 border border-sim-border h-48 flex items-center justify-center text-gray-500">
        No data yet
      </div>
    );
  }

  // Add capacity reference line data
  const data = history.map((h, i) => ({
    t: i,
    count: h.count,
    capacity: capacity,
    warning: capacity * 0.7,
    danger: capacity * 0.85,
  }));

  return (
    <div className="bg-sim-card rounded-lg p-4 border border-sim-border">
      <h3 className="text-sm font-bold text-gray-300 mb-3">Indoor Occupancy Over Time</h3>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="occupancyGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#3a3a5c" />
            <XAxis 
              dataKey="t" 
              stroke="#6b7280"
              tick={{ fontSize: 10 }}
              tickFormatter={(v) => v % 10 === 0 ? v : ''}
            />
            <YAxis 
              stroke="#6b7280"
              tick={{ fontSize: 10 }}
              domain={[0, 'dataMax + 10']}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#252540',
                border: '1px solid #3a3a5c',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#9ca3af' }}
            />
            {/* Warning threshold line */}
            <Line
              type="monotone"
              dataKey="warning"
              stroke="#eab308"
              strokeDasharray="5 5"
              dot={false}
              strokeWidth={1}
            />
            {/* Danger threshold line */}
            <Line
              type="monotone"
              dataKey="danger"
              stroke="#ef4444"
              strokeDasharray="5 5"
              dot={false}
              strokeWidth={1}
            />
            {/* Capacity line */}
            <Line
              type="monotone"
              dataKey="capacity"
              stroke="#6b7280"
              strokeDasharray="3 3"
              dot={false}
              strokeWidth={1}
            />
            {/* Main occupancy area */}
            <Area
              type="monotone"
              dataKey="count"
              stroke="#3b82f6"
              fill="url(#occupancyGradient)"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="flex gap-4 mt-2 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-yellow-500"></div>
          <span className="text-gray-400">70% Warning</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-red-500"></div>
          <span className="text-gray-400">85% Danger</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-gray-500"></div>
          <span className="text-gray-400">Capacity</span>
        </div>
      </div>
    </div>
  );
}
