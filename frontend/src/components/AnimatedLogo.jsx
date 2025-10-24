import React from 'react';

const AnimatedLogo = () => (
  <div className="relative flex w-full justify-center mb-6">
    <div className="logo-wrapper animate-float">
      <svg
        className="logo-mark"
        viewBox="0 0 256 256"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-labelledby="daily-report-logo-title"
      >
        <title id="daily-report-logo-title">Daily Report Name Injector logo</title>
        <defs>
          <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#4F46E5" />
            <stop offset="50%" stopColor="#6366F1" />
            <stop offset="100%" stopColor="#3B82F6" />
          </linearGradient>
        </defs>
        <rect x="24" y="24" width="208" height="208" rx="52" fill="url(#logoGradient)" />
        <path
          d="M66 174V82h52l44 53V82h28v92h-52l-44-53v53H66z"
          fill="#F8FAFC"
        />
        <circle cx="88" cy="98" r="9" fill="#C7D2FE" />
      </svg>
    </div>
  </div>
);

export default AnimatedLogo;
