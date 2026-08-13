import type { ReactNode } from 'react'

type PanelProps = {
  /** Accepts a Lucide icon component, React element, string emoji, or undefined */
  icon?: ReactNode
  /** Main heading text for the panel */
  title: string
  /** Optional badge text displayed in the header */
  badge?: string
  /** Additional CSS class names for custom styling */
  className?: string
  /** Content rendered inside the panel body */
  children: ReactNode
}

function Panel({ icon, title, badge, className = '', children }: PanelProps) {
  return (
    <section className={`panel ${className}`.trim()}>
      <header className="panel-header">
        {icon && (
          <span className="panel-icon" aria-hidden="true">
            {icon}
          </span>
        )}
        <h2 className="panel-title">{title}</h2>
        {badge && <span className="panel-badge">{badge}</span>}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  )
}

export default Panel