import React, { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { motion, useReducedMotion, useInView } from 'framer-motion';

const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

/* Route/page entrance wrapper */
export const Page: React.FC<{ children: ReactNode }> = ({ children }) => {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: EASE }}
    >
      {children}
    </motion.div>
  );
};

/* Staggered container + item for grids/lists */
export const Stagger: React.FC<{ children: ReactNode; className?: string }> = ({ children, className }) => (
  <motion.div
    className={className}
    initial="hidden"
    animate="visible"
    variants={{ visible: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } } }}
  >
    {children}
  </motion.div>
);

export const StaggerItem: React.FC<{ children: ReactNode; className?: string }> = ({ children, className }) => (
  <motion.div
    className={className}
    variants={{ hidden: { opacity: 0, y: 16 }, visible: { opacity: 1, y: 0 } }}
    transition={{ duration: 0.45, ease: EASE }}
  >
    {children}
  </motion.div>
);

/* Hover-lift card wrapper */
export const Lift: React.FC<{ children: ReactNode; className?: string; onClick?: () => void }> = ({
  children, className, onClick,
}) => (
  <motion.div
    className={className}
    onClick={onClick}
    whileHover={{ y: -4 }}
    transition={{ type: 'spring', stiffness: 300, damping: 22 }}
  >
    {children}
  </motion.div>
);

/* Animated count-up number */
export const CountUp: React.FC<{ value: number; duration?: number }> = ({ value, duration = 1100 }) => {
  const [n, setN] = useState(0);
  const reduce = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });

  useEffect(() => {
    if (!inView) return;
    if (reduce || value === 0) { setN(value); return; }
    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(Math.round(value * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, value, duration, reduce]);

  return <span ref={ref}>{n.toLocaleString()}</span>;
};

/* Severity / category donut (pure SVG + Motion) */
export interface DonutSeg {
  value: number;
  color: string;
  label: string;
}
export const Donut: React.FC<{ segments: DonutSeg[]; size?: number; thickness?: number; centerLabel?: string }> = ({
  segments, size = 180, thickness = 18, centerLabel,
}) => {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-border-color)" strokeWidth={thickness} opacity={0.5} />
        {segments.map((seg, i) => {
          const frac = seg.value / total;
          const dash = frac * c;
          const el = (
            <motion.circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={seg.color}
              strokeWidth={thickness}
              strokeLinecap="round"
              strokeDasharray={`${dash} ${c - dash}`}
              initial={{ strokeDashoffset: -c }}
              animate={{ strokeDashoffset: -(c - offset) }}
              transition={{ duration: 0.9, ease: EASE, delay: i * 0.08 }}
            />
          );
          offset += dash;
          return el;
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-display font-semibold text-text-primary">
          <CountUp value={total} />
        </span>
        {centerLabel && <span className="text-xs uppercase tracking-wider text-text-muted">{centerLabel}</span>}
      </div>
    </div>
  );
};

/* Re-export motion for ad-hoc use */
export { motion, useReducedMotion };
