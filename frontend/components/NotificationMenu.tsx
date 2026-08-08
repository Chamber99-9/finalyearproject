"use client";

import { useEffect, useMemo, useState } from "react";

type Notification = {
  id: string;
  title: string;
  message: string;
  read: boolean;
  created_at: string;
};

/**
 * Show a notification's timestamp in Nepal Time (NPT, UTC+5:45). The backend
 * stores created_at in UTC, so we format it in the Asia/Kathmandu timezone
 * regardless of where the viewer's browser is.
 */
function formatNepalTime(iso: string): string {
  try {
    return (
      new Date(iso).toLocaleString("en-GB", {
        timeZone: "Asia/Kathmandu",
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true
      }) + " NPT"
    );
  } catch {
    return new Date(iso).toLocaleString() + " NPT";
  }
}

export function NotificationMenu() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadNotifications() {
      try {
        const response = await fetch("/api/notifications");
        const payload = await response.json().catch(() => ({}));

        if (!response.ok) {
          setError(payload.error ?? "Could not load notifications.");
          return;
        }

        setNotifications(payload.notifications ?? []);
      } catch {
        setError("Could not reach notification service.");
      }
    }

    loadNotifications();
  }, []);

  const unreadCount = useMemo(
    () => notifications.filter((notification) => !notification.read).length,
    [notifications]
  );

  async function markRead(notificationId: string) {
    setNotifications((current) =>
      current.map((notification) =>
        notification.id === notificationId
          ? { ...notification, read: true }
          : notification
      )
    );

    await fetch(`/api/notifications/${encodeURIComponent(notificationId)}/read`, {
      method: "PUT"
    }).catch(() => undefined);
  }

  const hasUnread = unreadCount > 0;

  return (
    <div className="relative">
      <button
        aria-label={hasUnread ? `Notifications, ${unreadCount} unread` : "Notifications"}
        className="relative rounded-full p-2 text-slate-600 transition duration-200 hover:scale-110 hover:bg-emerald-50 hover:text-emerald-800"
        onClick={() => setIsOpen((current) => !current)}
        type="button"
      >
        <svg
          className={`h-6 w-6 ${hasUnread ? "animate-bell" : ""}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"
          />
        </svg>
        {hasUnread ? (
          <>
            <span className="absolute right-1 top-1 h-2.5 w-2.5 animate-ping rounded-full bg-emerald-500" />
            <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-emerald-600 px-1 text-xs font-bold text-white shadow">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          </>
        ) : null}
      </button>

      {isOpen ? (
        <div className="absolute right-0 z-50 mt-2 w-80 rounded-lg border border-slate-200 bg-white shadow-lg">
          <div className="border-b border-slate-200 px-4 py-3">
            <p className="font-semibold text-slate-950">Notifications</p>
          </div>
          <div className="max-h-96 overflow-auto">
            {error ? (
              <p className="px-4 py-3 text-sm text-red-700">{error}</p>
            ) : notifications.length > 0 ? (
              notifications.slice(0, 8).map((notification) => (
                <button
                  className={`block w-full border-b border-slate-100 px-4 py-3 text-left text-sm hover:bg-slate-50 ${
                    notification.read ? "bg-white" : "bg-emerald-50"
                  }`}
                  key={notification.id}
                  onClick={() => markRead(notification.id)}
                  type="button"
                >
                  <span className="font-semibold text-slate-950">
                    {notification.title}
                  </span>
                  <span className="mt-1 block leading-5 text-slate-600">
                    {notification.message}
                  </span>
                  <span className="mt-2 block text-xs text-slate-500">
                    {formatNepalTime(notification.created_at)}
                  </span>
                </button>
              ))
            ) : (
              <p className="px-4 py-3 text-sm text-slate-600">No notifications yet.</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
