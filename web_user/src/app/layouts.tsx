import { Outlet } from "react-router-dom";
import { Header } from "@/widgets/header";
import { Footer } from "@/widgets/footer";

/** Standard page layout: sticky header + scrolling content + footer. */
export function RootLayout() {
  return (
    <div className="flex min-h-dvh flex-col">
      <Header />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}

/** Full-height layout for map / chat — no footer, content owns the viewport. */
export function BareLayout() {
  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <Header />
      <main className="min-h-0 flex-1">
        <Outlet />
      </main>
    </div>
  );
}
