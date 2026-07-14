import { Activity, ClipboardCheck, Gauge, Home, MonitorCog, PlaySquare, Wrench } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/", label: "运行总览", icon: Home },
  { to: "/incidents", label: "异常事件", icon: Activity },
  { to: "/approvals", label: "审批中心", icon: ClipboardCheck },
  { to: "/work-orders", label: "工单管理", icon: Wrench },
  { to: "/rpa-runs", label: "RPA 执行记录", icon: MonitorCog },
  { to: "/demo", label: "场景演示", icon: PlaySquare }
];

export function Layout() {
  return (
    <div className="min-h-screen bg-slate-200">
      <header className="border-b border-slate-400 bg-slate-900 text-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <Gauge className="h-6 w-6 text-teal-300" aria-hidden="true" />
            <div>
              <h1 className="text-base font-semibold">制造业异常响应中心</h1>
              <p className="text-xs text-slate-300">生产异常分析、审批、工单流转与自动化处理平台</p>
            </div>
          </div>
        </div>
      </header>
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 px-4 py-4 lg:grid-cols-[220px_1fr]">
        <nav className="panel h-fit">
          {links.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `flex items-center gap-2 border-b border-slate-200 px-3 py-3 text-sm font-medium ${
                    isActive ? "bg-teal-50 text-teal-900" : "text-slate-700 hover:bg-slate-50"
                  }`
                }
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {link.label}
              </NavLink>
            );
          })}
        </nav>
        <main className="min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
