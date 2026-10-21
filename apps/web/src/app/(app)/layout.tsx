import { AppSessionProvider } from "@/components/AppSession";
import { FeedbackWidget } from "@/components/FeedbackWidget";
import { Hubzy } from "@/components/hubzy/Hubzy";
import { PageTransition } from "@/components/PageTransition";
import { Rail } from "@/components/Rail";
import { ShellCrumbs } from "@/components/ShellCrumbs";
import { Topbar } from "@/components/Topbar";

/** Every signed-in page: the session guard, the top bar, the icon rail, the workspace, the Feedback panel and Hubzy. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppSessionProvider
      fallback={
        <div className="shell" aria-busy="true">
          <div className="topbar" />
          <div className="shell-body">
            <div className="rail" />
            <main className="workspace">
              <div className="page-content">
                <div className="skeleton" style={{ height: 72 }} />
                <div className="skeleton" style={{ height: 160 }} />
              </div>
            </main>
          </div>
        </div>
      }
    >
      <div className="shell">
        <Topbar />
        <div className="shell-body">
          <Rail />
          <main className="workspace">
            <ShellCrumbs />
            <PageTransition>{children}</PageTransition>
          </main>
        </div>
        <FeedbackWidget />
        <Hubzy />
      </div>
    </AppSessionProvider>
  );
}
