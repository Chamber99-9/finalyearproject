"use client";

import { useEffect, useMemo, useState } from "react";

type Notification = {
  id: string;
  title: string;
  message: string;
  read: boolean;
  created_at: string;
};

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

  return (
    <div className="relative">
      <button
        className="rounded-md px-3 py-2 text-sm font-medium transition hover:bg-emerald-50 hover:text-emerald-800"
        onClick={() => setIsOpen((current) => !current)}
        type="button"
      >
        Notifications
        {unreadCount > 0 ? (
          <span className="ml-2 rounded-full bg-emerald-700 px-2 py-0.5 text-xs font-bold text-white">
            {unreadCount}
          </span>
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
                    {new Date(notification.created_at).toLocaleString()}
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
