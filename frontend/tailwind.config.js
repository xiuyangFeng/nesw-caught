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
        ai: 'var(--ai)',
        'ai-2': 'var(--ai-2)',
      },
      borderRadius: {
        sm: 'var(--r-sm)',
        md: 'var(--r-md)',
        lg: 'var(--r-lg)',
        xl: 'var(--r-xl)',
      },
      boxShadow: {
        shell: 'var(--shadow)',
        glow: 'var(--glow-accent)',
        'glow-ai': 'var(--glow-ai)',
      },
      fontFamily: {
        sans: ['HarmonyOS Sans SC', 'Inter', 'IBM Plex Sans', 'PingFang SC', 'Hiragino Sans GB', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'IBM Plex Mono', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      backgroundImage: {
        app: 'var(--bg-accent)',
        'grad-ai': 'var(--grad-ai)',
      },
      screens: {
        shell: '1100px',
      },
    },
  },
  plugins: [],
};
