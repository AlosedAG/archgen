import { AppSessionProvider } from "@/components/AppSession";
import { Sidebar } from "@/components/Sidebar";

/** Every signed-in page: the session guard, the sidebar, the workspace. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppSessionProvider
      fallback={
        <div className="shell" aria-busy="true">
          <div className="sidebar" />
          <main className="workspace">
            <div className="page-header" style={{ minHeight: 178 }} />
            <div className="page-content">
              <div className="skeleton" style={{ height: 72 }} />
              <div className="skeleton" style={{ height: 160 }} />
            </div>
          </main>
        </div>
      }
    >
      <div className="shell">
        <Sidebar />
        <main className="workspace">{children}</main>
      </div>
    </AppSessionProvider>
  );
}
