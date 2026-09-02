import { useState, useEffect } from "react"
import { useThemeToken } from "../theme/useThemeToken";
import { useNavigate } from "react-router-dom";
import { Dropdown, Badge, Skeleton } from "antd";
import { BellOutlined, DeleteOutlined, InboxOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/zh-cn";
import { useNotificationStore, Notification } from "../store/notification";
import {
  getNotifications,
  markAllAsRead,
  deleteNotification,
} from "../api/notifications";

dayjs.extend(relativeTime);
dayjs.locale("zh-cn");

// 类型图标和颜色映射
const typeConfig: Record<string, { icon: string; color: string }> = {
  quota_low: { icon: "🔴", color: "#EF4444" },
  quota_increase: { icon: "🟢", color: "#22C55E" },
  quota_decrease: { icon: "🔵", color: "#3B82F6" },
  daily_report: { icon: "🟡", color: "#EAB308" },
  system: { icon: "⚪", color: "#94A3B8" },
};

const getTypeConfig = (type: string) => {
  return typeConfig[type] || typeConfig.system;
};

// 相对时间格式化
const formatRelativeTime = (dateStr: string) => {
  const date = dayjs(dateStr);
  const now = dayjs();
  const diffHours = now.diff(date, "hour");
  const diffDays = now.diff(date, "day");

  if (diffHours < 1) {
    return date.fromNow();
  } else if (diffHours < 24) {
    return `${diffHours}小时前`;
  } else if (diffDays === 1) {
    return "昨天";
  } else if (diffDays < 7) {
    return `${diffDays}天前`;
  } else {
    return date.format("MM月DD日");
  }
};

interface NotificationDropdownProps {
  trigger: React.ReactNode;
}

export default function NotificationDropdown({
  trigger,
}: NotificationDropdownProps) {
  const { token, isDark } = useThemeToken()
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const {
    notifications,
    markAllAsRead: markAllAsReadStore,
    removeNotification,
  } = useNotificationStore();

  // 打开时加载历史通知
  const handleOpenChange = async (isOpen: boolean) => {
    setOpen(isOpen);
    if (isOpen && notifications.length === 0) {
      setLoading(true);
      try {
        const res = await getNotifications({ page: 1, page_size: 20 });
        // 更新 store（这里简化处理，直接用返回数据）
        useNotificationStore.setState({
          notifications: res.items,
          unreadCount: res.unread_count,
        });
      } catch (error) {
        console.error("加载通知失败:", error);
      } finally {
        setLoading(false);
      }
    }
  };

  // 点击单条通知：关闭下拉，跳转 /notifications 并由页面解析 ?notif= 打开详情 drawer
  const handleNotificationClick = (
    notif: Notification,
    e: React.MouseEvent,
  ) => {
    e.stopPropagation();
    setOpen(false);
    navigate(`/notifications?notif=${notif.notif_id}`);
  };

  // 全部已读
  const handleMarkAllAsRead = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await markAllAsRead();
      markAllAsReadStore();
    } catch (error) {
      console.error("标记全部已读失败:", error);
    }
  };

  // 删除通知
  const handleDelete = async (notifId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteNotification(notifId);
      removeNotification(notifId);
    } catch (error) {
      console.error("删除通知失败:", error);
    }
  };

  // 渲染单个通知项
  const renderNotificationItem = (notif: Notification) => {
    const config = getTypeConfig(notif.type);
    return (
      <div
        key={notif.notif_id}
        onClick={(e) => handleNotificationClick(notif, e)}
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
          cursor: "pointer",
          transition: "background 0.2s",
          background: notif.is_read ? "transparent" : (isDark ? "rgba(59, 130, 246, 0.15)" : "rgba(59, 130, 246, 0.08)"),
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.04)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = notif.is_read ? "transparent" : (isDark ? "rgba(59, 130, 246, 0.15)" : "rgba(59, 130, 246, 0.08)");
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
          {/* 图标 */}
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: `${config.color}20`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 16,
              flexShrink: 0,
            }}
          >
            {config.icon}
          </div>

          {/* 内容 */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                color: notif.is_read ? token.colorTextSecondary : token.colorText,
                fontWeight: notif.is_read ? 400 : 500,
                fontSize: 13,
                marginBottom: 4,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {notif.title}
            </div>
            {notif.content && (
              <div
                style={{
                  color: token.colorTextSecondary,
                  fontSize: 12,
                  marginBottom: 4,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {notif.content}
              </div>
            )}
            <div style={{ color: token.colorTextSecondary, fontSize: 11 }}>
              {formatRelativeTime(notif.created_at)}
            </div>
          </div>

          {/* 删除按钮 */}
          <DeleteOutlined
            onClick={(e) => handleDelete(notif.notif_id, e)}
            style={{
              color: token.colorTextSecondary,
              fontSize: 12,
              cursor: "pointer",
              padding: 4,
              opacity: 0.6,
              transition: "opacity 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.opacity = "1";
              e.currentTarget.style.color = "#EF4444";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.opacity = "0.6";
              e.currentTarget.style.color = "#64748B";
            }}
          />
        </div>
      </div>
    );
  };

  // 通知内容面板
  const dropdownContent = (
    <div
      style={{
        width: 380,
        background: token.colorBgElevated,
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(255, 255, 255, 0.1)",
        borderRadius: 12,
        overflow: "hidden",
        boxShadow: "0 20px 40px rgba(0, 0, 0, 0.4)",
      }}
    >
      {/* 头部 */}
      <div
        style={{
          padding: "14px 16px",
          borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span style={{ color: token.colorText, fontWeight: 600, fontSize: 14 }}>
          通知
        </span>
        <span
          onClick={handleMarkAllAsRead}
          style={{
            color: token.colorPrimary,
            fontSize: 12,
            cursor: "pointer",
            transition: "color 0.2s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "#60A5FA";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "#3B82F6";
          }}
        >
          全部已读
        </span>
      </div>

      {/* 通知列表 */}
      <div style={{ maxHeight: 400, overflowY: "auto" }}>
        {loading ? (
          <div style={{ padding: 20 }}>
            <Skeleton active paragraph={{ rows: 3 }} />
          </div>
        ) : notifications.length === 0 ? (
          <div
            style={{
              padding: "40px 20px",
              textAlign: "center",
              color: token.colorTextSecondary,
            }}
          >
            <InboxOutlined
              style={{ fontSize: 40, marginBottom: 12, opacity: 0.5 }}
            />
            <div>暂无通知</div>
          </div>
        ) : (
          <>
            {notifications.slice(0, 10).map(renderNotificationItem)}
            {notifications.length > 10 && (
              <div
                style={{
                  padding: "12px 16px",
                  textAlign: "center",
                  borderTop: "1px solid rgba(255, 255, 255, 0.05)",
                }}
              >
                <span
                  style={{
                    color: token.colorPrimary,
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                  onClick={() => {
                    setOpen(false);
                    navigate("/notifications");
                  }}
                >
                  查看全部通知 &gt;
                </span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );

  return (
    <Dropdown
      popupRender={() => dropdownContent}
      trigger={["click"]}
      open={open}
      onOpenChange={handleOpenChange}
      placement="bottomRight"
    >
      {trigger}
    </Dropdown>
  );
}
