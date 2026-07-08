import React, { HTMLAttributes } from 'react';
import './Badge.css';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'primary' | 'secondary' | 'success' | 'warning' | 'danger';
}

export const Badge: React.FC<BadgeProps> = ({ 
  children, 
  variant = 'secondary', 
  className = '', 
  ...props 
}) => {
  return (
    <span className={`v-badge v-badge-${variant} ${className}`} {...props}>
      {children}
    </span>
  );
};
