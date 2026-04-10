import type { ReactNode } from "react";

interface AppShellProps {
  header: ReactNode;
  sidebar: ReactNode;
  main: ReactNode;
  secondary: ReactNode;
}

export function AppShell({ header, sidebar, main, secondary }: AppShellProps) {
  return (
    <div className="app-shell">
      <header className="app-shell__header">{header}</header>
      <aside className="app-shell__sidebar">{sidebar}</aside>
      <main className="app-shell__main">{main}</main>
      <aside className="app-shell__secondary">{secondary}</aside>
    </div>
  );
}
