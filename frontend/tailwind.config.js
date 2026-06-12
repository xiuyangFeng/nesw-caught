/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        'bg-elevated': 'var(--bg-elevated)',
        panel: 'var(--panel)',
        'panel-strong': 'var(--panel-strong)',
        'panel-stronger': 'var(--panel-stronger)',
        'panel-soft': 'var(--panel-soft)',
        field: 'var(--field-bg)',
        border: 'var(--border)',
        'border-strong': 'var(--border-strong)',
        text: 'var(--text)',
        'text-soft': 'var(--text-soft)',
        'text-faint': 'var(--text-faint)',
        muted: 'var(--muted)',
        positive: 'var(--positive)',
        negative: 'var(--negative)',
        success: 'var(--success)',
        danger: 'var(--danger)',
        neutral: 'var(--neutral)',
        warning: 'var(--warning)',
        accent: 'var(--accent)',
        system: 'var(--system)',
      },
      boxShadow: {
        shell: 'var(--shadow)',
        terminal: '0 18px 42px rgba(2, 6, 12, 0.34)',
        signal: '0 0 18px rgba(255, 159, 47, 0.35)',
      },
      fontFamily: {
        sans: ['IBM Plex Sans', 'PingFang SC', 'Hiragino Sans GB', 'sans-serif'],
        mono: ['IBM Plex Mono', 'SFMono-Regular', 'monospace'],
      },
      backgroundImage: {
        app: 'var(--bg-accent)',
        terminal:
          'linear-gradient(180deg, rgba(15, 24, 36, 0.96), rgba(10, 17, 27, 0.96)), radial-gradient(circle at top right, rgba(83, 194, 255, 0.08), transparent 26%)',
      },
      screens: {
        shell: '1100px',
      },
    },
  },
  plugins: [],
};
