import { AppSessionProvider } from "@/components/AppSession";
import { FeedbackWidget } from "@/components/FeedbackWidget";
import { PageTransition } from "@/components/PageTransition";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";

/** Every signed-in page: the session guard, the sidebar, the workspace, the Feedback panel. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppSessionProvider
      fallback={
        <div className="shell" aria-busy="true">
          <div className="sidebar" />
          <main className="workspace">
            <div className="page-header" style={{ minHeight: 130 }} />
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
        <main className="workspace">
          <Topbar />
          <PageTransition>{children}</PageTransition>
        </main>
        <FeedbackWidget />
      </div>
    </AppSessionProvider>
  );
}
