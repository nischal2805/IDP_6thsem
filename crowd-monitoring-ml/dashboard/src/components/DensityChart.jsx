import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';

export default function DensityChart({ history }) {
  const data = history.map((point, i) => ({
    t: i,
    count: point.count,
    persons: point.persons
  }));

  if (data.length === 0) {
    return (
      <div className="card h-64 flex items-center justify-center text-gray-500">
        Waiting for data...
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="font-bold mb-3">Crowd Density Over Time</h3>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="densityGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="personGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis 
              dataKey="t" 
              stroke="#64748b"
              tick={{ fontSize: 10 }}
            />
            <YAxis 
              stroke="#64748b"
              tick={{ fontSize: 10 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '8px',
              }}
            />
            <Area
              type="monotone"
              dataKey="count"
              stroke="#0ea5e9"
              fill="url(#densityGradient)"
              name="Density Count"
            />
            <Area
              type="monotone"
              dataKey="persons"
              stroke="#22c55e"
              fill="url(#personGradient)"
              name="Detected Persons"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="flex gap-4 mt-2 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-primary"></div>
          <span className="text-gray-400">Density</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-success"></div>
          <span className="text-gray-400">Persons</span>
        </div>
      </div>
    </div>
  );
}
