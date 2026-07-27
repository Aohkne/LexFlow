export default function AppLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <div className="flex h-screen overflow-hidden bg-background">{children}</div>;
}
