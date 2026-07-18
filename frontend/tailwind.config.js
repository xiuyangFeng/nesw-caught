/** @type {import('tailwindcss').Config} */

/**
 * 让"以 CSS 变量(十六进制值)定义的语义色"支持 Tailwind 的 `/透明度` 修饰符。
 * 默认下 `colors: { accent: 'var(--accent)' }` 时，`bg-accent/40` 会被编译期静默丢弃
 * （Tailwind 无法对非通道值套 alpha）。这里用函数式颜色 + `color-mix` 生成有效 CSS：
 *   bg-accent      → background-color: var(--accent)
 *   bg-accent/40   → background-color: color-mix(in srgb, var(--accent) calc(0.4 * 100%), transparent)
 * 既保留 main.css 里 `var(--accent)` 的原样用法，又救活全站 `/opacity` 写法。
 */
function withAlpha(variable) {
  return ({ opacityValue }) =>
    opacityValue === undefined
      ? `var(${variable})`
      : `color-mix(in srgb, var(${variable}) calc(${opacityValue} * 100%), transparent)`;
}

export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        bg: withAlpha('--bg'),
        'bg-elevated': withAlpha('--bg-elevated'),
        panel: withAlpha('--panel'),
        'panel-strong': withAlpha('--panel-strong'),
        'panel-stronger': withAlpha('--panel-stronger'),
        'panel-soft': withAlpha('--panel-soft'),
        field: withAlpha('--field-bg'),
        border: withAlpha('--border'),
        'border-strong': withAlpha('--border-strong'),
        text: withAlpha('--text'),
        'text-soft': withAlpha('--text-soft'),
        'text-faint': withAlpha('--text-faint'),
        muted: withAlpha('--muted'),
        positive: withAlpha('--positive'),
        negative: withAlpha('--negative'),
        success: withAlpha('--success'),
        danger: withAlpha('--danger'),
        neutral: withAlpha('--neutral'),
        warning: withAlpha('--warning'),
        accent: withAlpha('--accent'),
        system: withAlpha('--system'),
        ai: withAlpha('--ai'),
        'ai-2': withAlpha('--ai-2'),
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
        sans: ['HarmonyOS Sans SC', 'Inter', 'PingFang SC', 'Hiragino Sans GB', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'SFMono-Regular', 'Menlo', 'monospace'],
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
