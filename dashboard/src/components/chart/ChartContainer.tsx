import type { PropsWithChildren, ReactNode } from "react";

interface ChartContainerProps extends PropsWithChildren {
  title: string;
  subtitle?: string;
  aside?: ReactNode;
}

export function ChartContainer({ title, subtitle, aside, children }: ChartContainerProps) {
  return (
    <section className="chart-card">
      <header className="chart-card__header">
        <div>
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {aside ? <div className="chart-card__aside">{aside}</div> : null}
      </header>
      <div className="chart-card__body">{children}</div>
    </section>
  );
}
