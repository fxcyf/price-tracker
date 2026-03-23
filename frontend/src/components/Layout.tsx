import { NavLink, Outlet } from "react-router-dom";
import { LayoutDashboard, Settings, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";

const navItems = [
  { to: "/", label: "Products", icon: LayoutDashboard, end: true },
  { to: "/settings", label: "Settings", icon: Settings, end: false },
];

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar — desktop only */}
      <aside className="hidden lg:flex w-56 flex-col border-r bg-card">
        <div className="flex h-14 items-center gap-2 px-4">
          <TrendingDown className="h-5 w-5 text-primary" />
          <span className="text-sm font-semibold tracking-tight">Price Tracker</span>
        </div>
        <Separator />
        <nav className="flex-1 space-y-1 p-2">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main content — extra bottom padding on mobile for the nav bar */}
      <main className="flex-1 overflow-auto lg:pb-0" style={{ paddingBottom: "calc(4rem + env(safe-area-inset-bottom))" }}>
        <Outlet />
      </main>

      {/* Bottom nav bar — mobile/tablet only */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 flex border-t bg-card lg:hidden" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
        {navItems.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "flex flex-1 flex-col items-center justify-center gap-1 py-2 text-xs font-medium transition-colors",
                isActive ? "text-primary" : "text-muted-foreground"
              )
            }
          >
            <Icon className="h-5 w-5" />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
