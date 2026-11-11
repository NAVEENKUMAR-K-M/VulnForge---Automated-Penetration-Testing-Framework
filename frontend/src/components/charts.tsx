import React from 'react';
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, CartesianGrid,
} from 'recharts';

const tooltipStyle = {
  background: 'var(--color-surface-hover)',
  border: '1px solid var(--color-border-color)',
  borderRadius: 10,
  fontSize: 12,
  color: 'var(--color-text-primary)',
  boxShadow: '0 10px 30px -12px rgba(0,0,0,0.6)',
};

export interface Bar1 { name: string; value: number; color: string; }

export const SeverityBars: React.FC<{ data: Bar1[] }> = ({ data }) => (
  <ResponsiveContainer width="100%" height={Math.max(120, data.length * 38)}>
    <BarChart data={data} layout="vertical" margin={{ left: 4, right: 24, top: 4, bottom: 4 }}>
      <XAxis type="number" hide allowDecimals={false} />
      <YAxis
        type="category"
        dataKey="name"
        width={78}
        tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }}
        axisLine={false}
        tickLine={false}
      />
      <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
      <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={16} label={{ position: 'right', fill: 'var(--color-text-secondary)', fontSize: 12 }}>
        {data.map((d, i) => <Cell key={i} fill={d.color} />)}
      </Bar>
    </BarChart>
  </ResponsiveContainer>
);

export interface Point { label: string; value: number; }

export const ActivityArea: React.FC<{ data: Point[]; height?: number }> = ({ data, height = 220 }) => (
  <ResponsiveContainer width="100%" height={height}>
    <AreaChart data={data} margin={{ top: 10, right: 12, left: -18, bottom: 0 }}>
      <defs>
        <linearGradient id="vfArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.45} />
          <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
        </linearGradient>
      </defs>
      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-color)" vertical={false} opacity={0.5} />
      <XAxis dataKey="label" tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
      <YAxis tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} width={32} />
      <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: 'var(--color-primary)', strokeWidth: 1, strokeDasharray: '4 4' }} />
      <Area type="monotone" dataKey="value" stroke="var(--color-primary)" strokeWidth={2.5} fill="url(#vfArea)" animationDuration={900} />
    </AreaChart>
  </ResponsiveContainer>
);
