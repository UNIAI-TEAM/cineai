import { useState } from "react";

import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import {

  Bell,

  Clapperboard,

  FileVideo,

  Film,

  Image,

  Layers,

  LayoutDashboard,

  ListVideo,

  LogOut,

  Maximize2,

  Menu,

  Receipt,

  Settings,

  Shapes,

  Users,

  Wallet,

} from "lucide-react";

import { clearAuth, getCachedUser } from "@/lib/auth";

import { useCurrency } from "@/lib/currency";

import { cn } from "@/lib/utils";



type NavItem = {

  to: string;

  label: string;

  icon: typeof LayoutDashboard;

  end?: boolean;

  matchPrefix?: boolean;

};



type NavGroup = {

  label: string;

  items: NavItem[];

};



const navGroups: NavGroup[] = [

  {

    label: "Tổng quan",

    items: [{ to: "/", label: "Tổng quan", icon: LayoutDashboard, end: true }],

  },

  {

    label: "Kinh doanh",

    items: [

      { to: "/users", label: "Người dùng", icon: Users },

      { to: "/orders", label: "Đơn nạp tiền", icon: Receipt },
      { to: "/finance", label: "Tài chính", icon: Wallet },

      { to: "/projects", label: "Dự án video ngắn", icon: Clapperboard },

      { to: "/works", label: "Duyệt tác phẩm", icon: FileVideo },

    ],

  },

  {

    label: "Phim ngắn",

    items: [

      { to: "/drama-projects", label: "Dự án phim ngắn", icon: Film, matchPrefix: true },

      { to: "/drama-assets", label: "Tư liệu", icon: Image, matchPrefix: true },

      { to: "/drama-episodes", label: "Tập phim", icon: ListVideo, matchPrefix: true },

      { to: "/drama-fragments", label: "Phân cảnh", icon: Layers, matchPrefix: true },

    ],

  },

  {

    label: "Tài nguyên",

    items: [

      { to: "/templates", label: "Mẫu", icon: Shapes },

      { to: "/queues", label: "Trung tâm tác vụ", icon: Layers },

    ],

  },

  {

    label: "Hệ thống",

    items: [{ to: "/settings", label: "Cài đặt", icon: Settings }],

  },

];



const titles: Record<string, string> = {

  "/": "Tổng quan",

  "/users": "Người dùng",

  "/orders": "Đơn nạp tiền",
  "/finance": "Tài chính",

  "/projects": "Dự án video ngắn",

  "/drama-projects": "Dự án phim ngắn",

  "/drama-assets": "Kho tư liệu",

  "/drama-episodes": "Tập phim",

  "/drama-fragments": "Phân cảnh",

  "/works": "Duyệt tác phẩm",

  "/templates": "Mẫu",

  "/settings": "Cài đặt",

  "/queues": "Trung tâm tác vụ",

};



function resolveTitle(pathname: string): string {

  if (pathname.startsWith("/drama-projects/")) return "Chi tiết dự án phim ngắn";

  if (pathname.startsWith("/drama-assets/")) return "Chi tiết tư liệu";

  if (pathname.startsWith("/drama-episodes/")) return "Chi tiết tập";

  if (pathname.startsWith("/drama-fragments/")) return "Chi tiết phân cảnh";

  return titles[pathname] ?? "Trang quản trị";

}



// Admin shell: dark sidebar + glass top bar

export function AdminLayout() {

  const navigate = useNavigate();

  const location = useLocation();

  const user = getCachedUser();

  const { currency, options: currencyOptions, setCurrency } = useCurrency();

  /*

   * collapsed sidebar collapsed state

   */

  const [collapsed, setCollapsed] = useState(false);



  // Logout and return to login

  function handleLogout() {

    clearAuth();

    navigate("/login");

  }



  const title = resolveTitle(location.pathname);

  const initial = (user?.nickname || user?.email || "A").slice(0, 1).toUpperCase();



  return (

    <div className={cn("admin-app", collapsed && "is-collapsed")}>

      <aside className="admin-sidebar">

        <div className="admin-brand">

          <img src="/logo.svg" alt="CineAI" className="admin-brand-mark" width={38} height={38} />

          {!collapsed && (

            <div>

              <div className="admin-brand-name">Cine<span className="admin-brand-ai">AI</span></div>

              <div className="admin-brand-sub">Trang quản trị</div>

            </div>

          )}

        </div>

        <nav className="admin-nav">

          {navGroups.map((group) => (

            <div key={group.label} className="admin-nav-group">

              {!collapsed ? <div className="admin-nav-group-label">{group.label}</div> : null}

              {group.items.map((item) => (

                <NavLink

                  key={item.to}

                  to={item.to}

                  end={item.end ?? !item.matchPrefix}

                  className={({ isActive }) =>

                    cn(

                      "admin-nav-item",

                      (isActive || (item.matchPrefix && location.pathname.startsWith(`${item.to}/`))) &&

                        "is-active",

                    )

                  }

                  title={item.label}

                >

                  <item.icon className="h-[18px] w-[18px] shrink-0" />

                  {!collapsed && <span>{item.label}</span>}

                </NavLink>

              ))}

            </div>

          ))}

        </nav>

        <div className="admin-user-card">

          <div className="admin-avatar">{initial}</div>

          {!collapsed && (

            <div className="min-w-0 flex-1">

              <div className="truncate text-[13px] font-medium text-[#e8f0eb]">{user?.email}</div>

              <div className="text-xs text-[rgba(240,245,242,0.45)]">Quản trị viên cấp cao</div>

            </div>

          )}

          <button type="button" className="admin-icon-btn !text-[rgba(240,245,242,0.55)] hover:!text-[#e8f0eb]" onClick={handleLogout} title="Đăng xuất">

            <LogOut className="h-4 w-4" />

          </button>

        </div>

      </aside>



      <div className="admin-main">

        <header className="admin-topbar">

          <div className="flex items-center gap-3">

            <button

              type="button"

              className="admin-icon-btn"

              onClick={() => setCollapsed((v) => !v)}

              aria-label="Thu gọn thanh bên"

            >

              <Menu className="h-4 w-4" />

            </button>

            <div>

              <div className="admin-topbar-title">{title}</div>

              <div className="admin-topbar-crumb">CineAI · Quản trị vận hành</div>

            </div>

          </div>

          <div className="flex items-center gap-1">

            <div className="admin-currency-toggle" role="group" aria-label="Tiền tệ hiển thị" title="Tiền tệ hiển thị số tiền trên toàn trang">

              {currencyOptions.map((code) => (

                <button

                  key={code}

                  type="button"

                  className={cn("admin-currency-toggle-btn", code === currency && "is-active")}

                  aria-pressed={code === currency}

                  onClick={() => setCurrency(code)}

                >

                  {code}

                </button>

              ))}

            </div>

            <button type="button" className="admin-icon-btn" title="Thông báo">

              <Bell className="h-4 w-4" />

            </button>

            <button

              type="button"

              className="admin-icon-btn"

              title="Toàn màn hình"

              onClick={() => {

                if (!document.fullscreenElement) void document.documentElement.requestFullscreen();

                else void document.exitFullscreen();

              }}

            >

              <Maximize2 className="h-4 w-4" />

            </button>

          </div>

        </header>

        <main className="admin-content">

          <Outlet />

        </main>

      </div>

    </div>

  );

}


