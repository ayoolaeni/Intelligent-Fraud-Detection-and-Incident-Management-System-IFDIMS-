import React, { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import * as api from "../api/endpoints";
import { formatDateTime } from "./format";

const NAV_ITEMS: { to: string; label: string; roles?: string[] }[] = [
  { to: "/", label: "Overview" },
  { to: "/alerts", label: "Alerts", roles: ["analyst", "supervisor"] },
  { to: "/cases", label: "Cases", roles: ["analyst", "supervisor", "admin"] },
  { to: "/transactions", label: "Transactions" },
  { to: "/reports", label: "Reports", roles: ["supervisor", "admin"] },
  { to: "/admin/users", label: "Users", roles: ["admin"] },
  { to: "/admin/settings", label: "Settings", roles: ["admin"] },
  { to: "/admin/models", label: "Models", roles: ["admin"] },
  { to: "/admin/audit", label: "Audit log", roles: ["admin"] },
];

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [showNotifications, setShowNotifications] = useState(false);

  const { data: notifications } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.listNotifications(),
    refetchInterval: 15000,
  });

  const unreadCount = notifications?.filter((n) => !n.is_read).length ?? 0;

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const visibleItems = NAV_ITEMS.filter((item) => !item.roles || (user && item.roles.includes(user.role)));

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-gray-200 bg-white">
        <div className="border-b border-gray-200 p-4">
          <span className="text-lg font-bold text-gray-900">IFDIMS</span>
        </div>
        <nav className="flex flex-col gap-1 p-3">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `rounded px-3 py-2 text-sm font-medium ${
                  isActive ? "bg-blue-50 text-blue-700" : "text-gray-600 hover:bg-gray-50"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
          <div />
          <div className="flex items-center gap-4">
            <div className="relative">
              <button
                onClick={() => setShowNotifications((s) => !s)}
                className="relative rounded p-2 text-gray-500 hover:bg-gray-100"
                aria-label="Notifications"
              >
                Notifications
                {unreadCount > 0 && (
                  <span className="absolute -right-1 -top-1 rounded-full bg-red-600 px-1.5 text-xs text-white">
                    {unreadCount}
                  </span>
                )}
              </button>
              {showNotifications && (
                <div className="absolute right-0 z-10 mt-2 w-80 rounded border border-gray-200 bg-white shadow-lg">
                  <div className="flex items-center justify-between border-b p-2">
                    <span className="text-sm font-medium">Notifications</span>
                    <button
                      className="text-xs text-blue-600 hover:underline"
                      onClick={() => api.markAllNotificationsRead()}
                    >
                      Mark all read
                    </button>
                  </div>
                  <div className="max-h-96 overflow-y-auto">
                    {(notifications ?? []).length === 0 && (
                      <p className="p-3 text-sm text-gray-500">No notifications</p>
                    )}
                    {(notifications ?? []).map((n) => (
                      <Link
                        key={n.notification_id}
                        to={n.link ?? "#"}
                        onClick={() => {
                          api.markNotificationRead(n.notification_id);
                          setShowNotifications(false);
                        }}
                        className={`block border-b p-3 text-sm hover:bg-gray-50 ${n.is_read ? "text-gray-500" : "font-medium text-gray-900"}`}
                      >
                        <p>{n.message}</p>
                        <p className="text-xs text-gray-400">{formatDateTime(n.created_at)}</p>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="text-right text-sm">
              <div className="font-medium text-gray-900">{user?.full_name}</div>
              <div className="text-gray-500">{user?.role}</div>
            </div>
            <Link to="/account" className="text-sm text-blue-600 hover:underline">
              My account
            </Link>
            <button onClick={handleLogout} className="text-sm text-gray-500 hover:underline">
              Log out
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
