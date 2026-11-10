import React from 'react';
import type { ButtonHTMLAttributes } from 'react';
import './Button.css';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading,
  leftIcon,
  className = '',
  disabled,
  ...props
}) => {
  const classes = ['v-btn', `v-btn-${variant}`, `v-btn-${size}`, className]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      className={classes}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <span className="v-btn-spinner" />
      ) : leftIcon ? (
        <span className="v-btn-icon">{leftIcon}</span>
      ) : null}
      {children}
    </button>
  );
};
