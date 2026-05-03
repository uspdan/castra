import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function WeeklyActivity({ data = [] }) {
  return (
    <div className="rounded-lg p-4" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
      <h3 className="text-sm font-bold mb-3 font-mono" style={{ color: 'var(--text-secondary)' }}>WEEKLY ACTIVITY</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} barGap={2}>
          <XAxis dataKey="day" tick={{ fill: '#4A5568', fontSize: 11, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#4A5568', fontSize: 11, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{ background: '#0D1117', border: '1px solid #141C28', borderRadius: 8, fontSize: 12, fontFamily: 'JetBrains Mono' }}
            labelStyle={{ color: '#8899AA' }}
          />
          <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'JetBrains Mono' }} />
          <Bar dataKey="red" name="Red Team" stackId="a" fill="#FF3E6C" radius={[0, 0, 0, 0]} />
          <Bar dataKey="blue" name="Blue Team" stackId="a" fill="#00C8FF" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
