import defaultAvatar from "../../assets/default-avatar.webp";
import { userDisplayName } from "../../utils/userDisplayName.mjs";
import { useState, useEffect, useMemo } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Tour,
  Layout,
  Menu,
  Avatar,
  Dropdown,
  MenuProps,
  Badge,
  Tooltip,
  Modal,
  ColorPicker,
  Radio,
  Space,
} from "antd";
import {
  DashboardOutlined,
  MessageOutlined,
  KeyOutlined,
  BarChartOutlined,
  SettingOutlined,
  TeamOutlined,
  CloudOutlined,
  AppstoreOutlined,
  DollarOutlined,
  LogoutOutlined,
  BellOutlined,
  FileSearchOutlined,
  LoginOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons";
import { useAuthStore } from "../../store/auth";
import { useThemeToken } from "../../theme/useThemeToken";
import { useTheme } from "../../theme";
import NotificationDropdown from "../NotificationDropdown";
import { useNotificationStore } from "../../store/notification";
import { useSwrData } from "../../hooks/useSwr";
import { useDefaultModelGroupWarning } from "../../hooks/useDefaultModelGroupWarning";
import { canReadAdminPath, defaultAdminPath, hasPermission } from "../../utils/adminPermissions.mjs";

const { Sider } = Layout;

// Layout 常量
const SIDEBAR_WIDTH = 220;
const SIDEBAR_COLLAPSED_WIDTH = 64;
const HEADER_HEIGHT = 56;
const COLLAPSE_STORAGE_KEY = "token-manager-sidebar-collapsed";

// 根据路由生成页面标题
const getPageTitle = (pathname: string): string => {
  const map: Record<string, string> = {
    "/dashboard": "仪表盘",
    "/api-keys": "API Key 管理",
    "/chat": "AI 对话",
    "/stats": "仪表盘",
    "/notifications": "消息通知",
    "/approvals": "自助申请与审批",
    "/admin/approvals": "审批管理",
    "/admin/users": "用户管理",
    "/admin/projects": "项目管理",
    "/admin/billing": "月度预算",
    "/admin/billing/budgets": "月度预算",
    "/admin/billing/reservations": "预扣与结算",
    "/admin/billing/reconciliation": "对账管理",
    "/admin/departments": "部门管理",
    "/admin/department-dashboard": "部门仪表盘",
    "/admin/channels": "渠道管理",
    "/admin/health": "渠道健康看板",
    "/admin/roles": "角色与权限",
    "/admin/models": "模型管理",
    "/admin/model-groups": "模型分组",
    "/admin/logs/operations": "操作日志",
    "/admin/logs/logins": "登录日志",
    "/admin/logs/routes": "路由监控",
    "/settings": "个人设置",
  };
  return map[pathname] ?? "Token Manager";
};

const roleLabel = (role?: string) => {
  if (role === "admin") return "管理员";
  if (role === "department_admin") return "部门管理员";
  if (role === "auditor") return "审计只读";
  if (role === "user") return "普通用户";
  return "";
};

const MainLayout = () => {
  const { token: themeToken, isDark } = useThemeToken();
  const { theme, setTheme, themeOptions, customColor, customMode, setCustomTheme } = useTheme();
  const [customThemeOpen, setCustomThemeOpen] = useState(false);
  const navigate = useNavigate();

  // 主题菜单项 - 使用 CSS 变量
  const themeMenuItems = useMemo(
    () =>
      [...themeOptions.map((option) => ({
        key: option.name,
        label: (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14 }}>{option.icon}</span>
            <span>{option.label}</span>
            {theme === option.name && (
              <span
                style={{ marginLeft: "auto", color: "var(--color-primary)" }}
              >
                ✓
              </span>
            )}
          </div>
        ),
        onClick: () => setTheme(option.name),
      })), {
        key: "custom",
        label: theme === "custom" ? "🎨 自定义主题 ✓" : "🎨 自定义主题",
        onClick: () => { setTheme("custom"); setCustomThemeOpen(true); },
      }],
    [theme, setTheme, themeOptions],
  );
  const location = useLocation();
  const { token, user, logout } = useAuthStore();
  const { unreadCount } = useNotificationStore();
  const permissions = user?.permissions || [];
  const isAdmin = hasPermission(permissions, "admin:read");
  const canManageDepartments = hasPermission(permissions, "department:read");
  const { needsAttention: showDefaultGroupDot } =
    useDefaultModelGroupWarning(isAdmin);

  // 判断是否为亮色主题
  const isLightTheme = !isDark;

  // 初始化折叠状态,优先从 localStorage 读取
  const [tourOpen, setTourOpen] = useState(false);

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(COLLAPSE_STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    if (!token) {
      navigate("/login");
    }
  }, [token, navigate]);

  // 引导检测：使用 SWR 获取 API Keys
  const { data: apiKeysData } = useSwrData<{total: number; items: any[]}>(
    token ? "/api-keys" : null,
    { revalidateOnFocus: false, revalidateOnReconnect: false }
  );

  useEffect(() => {
    if (apiKeysData && (!apiKeysData.items || apiKeysData.items.length === 0)) {
      setTourOpen(true);
    }
  }, [apiKeysData]);

  const handleTourFinish = () => {
    setTourOpen(false);
  };

  // 持久化折叠状态
  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_STORAGE_KEY, String(collapsed));
    } catch {
      // 忽略存储异常(隐私模式等)
    }
  }, [collapsed]);

  const menuItems: MenuProps["items"] = [
    {
      key: defaultAdminPath(permissions),
      icon: <DashboardOutlined />,
      label: "仪表盘",
    },
    { key: "/notifications", icon: <BellOutlined />, label: "消息通知" },
    { key: "/approvals", icon: <FileSearchOutlined />, label: "申请与审批" },
    { key: "/api-keys", icon: <KeyOutlined />, label: "API Key" },
    { key: "/chat", icon: <MessageOutlined />, label: "AI 对话" },
    ...(isAdmin || canManageDepartments
      ? [
          {
            key: "admin",
            icon: <AppstoreOutlined />,
            label: "管理后台",
            children: [
              { key: "/admin/approvals", icon: <FileSearchOutlined />, label: "审批管理" },
              { key: "/admin/departments", icon: <TeamOutlined />, label: "部门管理" },
              { key: "/admin/projects", icon: <AppstoreOutlined />, label: "项目管理" },
              { key: "/admin/billing/budgets", icon: <DollarOutlined />, label: "月度预算" },
              { key: "/admin/billing/reservations", icon: <DollarOutlined />, label: "预扣与结算" },
              { key: "/admin/billing/reconciliation", icon: <FileSearchOutlined />, label: "对账管理" },
              {
                key: "/admin/users",
                icon: <TeamOutlined />,
                label: "用户管理",
              },
              {
                key: "/admin/channels",
                icon: <CloudOutlined />,
                label: "渠道管理",
              },
              {
                key: "/admin/health",
                icon: <BarChartOutlined />,
                label: "渠道健康",
              },
              { key: "/admin/roles", icon: <TeamOutlined />, label: "角色与权限" },
              {
                key: "/admin/models",
                icon: <AppstoreOutlined />,
                label: "模型管理",
              },
              {
                key: "/admin/model-groups",
                icon: <UnorderedListOutlined />,
                label: (
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    模型分组
                    {showDefaultGroupDot && (
                      <span
                        aria-label="缺少默认模型分组"
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: "50%",
                          background: "#ff4d4f",
                          display: "inline-block",
                          flexShrink: 0,
                        }}
                      />
                    )}
                  </span>
                ),
              },
              {
                key: "/admin/logs/operations",
                icon: <FileSearchOutlined />,
                label: "操作日志",
              },
              {
                key: "/admin/logs/logins",
                icon: <LoginOutlined />,
                label: "登录日志",
              },
              {
                key: "/admin/logs/routes",
                icon: <FileSearchOutlined />,
                label: "路由监控",
              },
            ].filter((item) => canReadAdminPath(item.key, permissions)),
          },
        ]
      : []),
    { key: "/settings", icon: <SettingOutlined />, label: "个人设置" },
  ];

  const tourSteps = [
    {
      title: 'API Key 管理',
      description: '在这里创建和管理您的 API Key，开始使用平台服务',
      target: () => {
        const items = document.querySelectorAll('.ant-menu-item');
        for (const item of items) {
          if (item.textContent?.trim() === 'API Key') return item as HTMLElement;
        }
        return null;
      },
    },
    {
      title: '仪表盘',
      description: '查看用量统计和账户概览',
      target: () => {
        const items = document.querySelectorAll('.ant-menu-item');
        for (const item of items) {
          if (item.textContent?.trim() === '仪表盘') return item as HTMLElement;
        }
        return null;
      },
    },
    {
      title: '消息通知',
      description: '查看系统通知和重要提醒',
      target: () => {
        const items = document.querySelectorAll('.ant-menu-item');
        for (const item of items) {
          if (item.textContent?.trim() === '消息通知') return item as HTMLElement;
        }
        return null;
      },
    },
  ];

  const userMenuItems: MenuProps["items"] = [
    {
      key: "profile",
      label: (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "4px 0",
          }}
        >
          <Avatar src={user?.avatar_url || defaultAvatar}
            size={36}
            style={{
              background:
                "linear-gradient(135deg, var(--color-primary-hover) 0%, var(--color-primary) 100%)",
              fontSize: 14,
              fontWeight: 600,
              flexShrink: 0,
            }}
          >
            {userDisplayName(user).charAt(0).toUpperCase() || "U"}
          </Avatar>
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                color: "var(--color-foreground)",
                fontWeight: 600,
                fontSize: 13,
                whiteSpace: "nowrap",
              }}
            >
              {userDisplayName(user)}
            </div>
            <div
              style={{
                color: "var(--color-text-secondary)",
                fontSize: 11,
                whiteSpace: "nowrap",
                maxWidth: 160,
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {user?.email}
            </div>
          </div>
        </div>
      ),
      disabled: true,
    },
    { type: "divider" },
    {
      key: "settings",
      icon: <SettingOutlined />,
      label: "个人设置",
      onClick: () => navigate("/settings"),
    },
    {
      key: "logout",
      icon: <LogoutOutlined />,
      label: "退出登录",
      danger: true,
      onClick: () => {
        logout();
        navigate("/login");
      },
    },
  ];

  const pageTitle = getPageTitle(location.pathname);
  const userRoleText = roleLabel(user?.role);

  // 动态计算菜单主题
  const menuTheme = isLightTheme ? "light" : "dark";

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--color-background)",
      }}
    >
      <Modal
        title="自定义主题"
        open={customThemeOpen}
        onCancel={() => setCustomThemeOpen(false)}
        onOk={() => setCustomThemeOpen(false)}
        okText="完成"
        cancelButtonProps={{ style: { display: "none" } }}
      >
        <Space direction="vertical" size={20} style={{ width: "100%", padding: "16px 0" }}>
          <Space>
            <span>主题主色</span>
            <ColorPicker
              value={customColor}
              showText
              format="hex"
              disabledAlpha
              onChange={color => setCustomTheme(color.toHexString(), customMode)}
            />
          </Space>
          <Space>
            <span>背景模式</span>
            <Radio.Group
              value={customMode}
              optionType="button"
              options={[{ label: "浅色", value: "light" }, { label: "深色", value: "dark" }]}
              onChange={event => setCustomTheme(customColor, event.target.value)}
            />
          </Space>
          <span style={{ color: themeToken.colorTextSecondary }}>调整后实时生效，并自动保存到当前浏览器。</span>
        </Space>
      </Modal>
      <Layout style={{ minHeight: "100vh" }}>
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          width={SIDEBAR_WIDTH}
          collapsedWidth={SIDEBAR_COLLAPSED_WIDTH}
          style={{
            background: "var(--sider-bg)",
            borderRight: "1px solid var(--color-border)",
            position: "fixed",
            left: 0,
            top: 0,
            bottom: 0,
            zIndex: 100,
            overflow: "hidden",
          }}
          trigger={null}
        >
          {/* Logo 区域 */}
          <div
            style={{
              height: HEADER_HEIGHT,
              display: "flex",
              alignItems: "center",
              justifyContent: collapsed ? "center" : "flex-start",
              padding: collapsed ? "0" : "0 20px",
              borderBottom: "1px solid var(--color-border)",
              transition: "all 0.3s",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                cursor: "pointer",
              }}
              onClick={() => navigate("/")}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background:
                    "linear-gradient(135deg, var(--color-primary-hover) 0%, var(--color-primary) 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#fff",
                  fontWeight: 700,
                  fontSize: 14,
                  flexShrink: 0,
                }}
              >
                TM
              </div>
              {!collapsed && (
                <span
                  style={{
                    color: "var(--color-foreground)",
                    fontSize: 16,
                    fontWeight: 700,
                    fontFamily: "'DM Sans', sans-serif",
                    whiteSpace: "nowrap",
                  }}
                >
                  Token Manager
                </span>
              )}
            </div>
          </div>

          {/* 菜单 - 根据主题动态调整 */}
          <Menu
            theme={menuTheme}
            mode="inline"
            selectedKeys={[location.pathname]}
            defaultOpenKeys={isAdmin ? ["admin"] : []}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
            style={{
              background: "transparent",
              borderRight: "none",
              marginTop: 8,
              // 预留 Logo、顶部间距和底部折叠按钮（36 + 16 * 2 + 1）的高度
              maxHeight: `calc(100% - ${HEADER_HEIGHT + 8 + 69}px)`,
              overflowY: "auto",
              overflowX: "hidden",
            }}
          />

          {/* 折叠按钮 */}
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              padding: "16px",
              borderTop: "1px solid var(--color-border)",
              background: "var(--sider-bg)",
            }}
          >
            <button
              onClick={() => setCollapsed(!collapsed)}
              style={{
                width: "100%",
                height: 32,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "var(--color-muted)",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                cursor: "pointer",
                color: "var(--color-text-secondary)",
                transition: "all 0.2s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--menu-hover-bg)";
                e.currentTarget.style.borderColor = "var(--color-primary)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "var(--color-muted)";
                e.currentTarget.style.borderColor = "var(--color-border)";
              }}
            >
              {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </button>
          </div>
        </Sider>

        <Layout
          style={{
            marginLeft: collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH,
            transition: "margin-left 0.2s",
            background: "var(--color-background)",
          }}
        >
          <header
            style={{
              height: HEADER_HEIGHT,
              background: "var(--header-bg)",
              borderBottom: "1px solid var(--color-border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "0 24px",
              position: "sticky",
              top: 0,
              zIndex: 99,
              backdropFilter: "blur(20px)",
              transition: "background 0.3s",
            }}
          >
            {/* 左侧：页面标题 */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
              }}
            >
              <h1
                style={{
                  margin: 0,
                  fontSize: 18,
                  fontWeight: 600,
                  color: "var(--color-text)",
                  fontFamily: "'DM Sans', sans-serif",
                }}
              >
                {pageTitle}
              </h1>
            </div>

            {/* 右侧：操作区 */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              {/* 主题切换 */}
              <Dropdown
                menu={{
                  items: themeMenuItems,
                }}
                placement="bottomRight"
                trigger={["click"]}
              >
                <Tooltip title="切换主题" placement="bottom">
                  <button
                    type="button"
                    aria-label="切换主题"
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 8,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      cursor: "pointer",
                      background: "transparent",
                      border: "none",
                      transition: "all 0.2s ease",
                    }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background =
                        "var(--menu-hover-bg)")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background = "transparent")
                    }
                  >
                    <span style={{ fontSize: 16 }}>
                      {themeOptions.find((t) => t.name === theme)?.icon || "🎨"}
                    </span>
                  </button>
                </Tooltip>
              </Dropdown>

              <NotificationDropdown
                trigger={
                  <Tooltip title="通知" placement="bottom">
                    <button
                      type="button"
                      aria-label="通知"
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 8,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer",
                        background: "transparent",
                        border: "none",
                        transition: "all 0.2s ease",
                        position: "relative",
                      }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.background =
                          "var(--menu-hover-bg)")
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.background = "transparent")
                      }
                    >
                      <Badge count={unreadCount} size="small" offset={[-2, 2]}>
                        <BellOutlined
                          style={{
                            color: "var(--color-text-secondary)",
                            fontSize: 16,
                          }}
                        />
                      </Badge>
                    </button>
                  </Tooltip>
                }
              />

              {/* 用户信息下拉 */}
              <Dropdown
                menu={{
                  items: userMenuItems,
                  style: {
                    background: themeToken.colorBgElevated,
                    backdropFilter: "blur(20px)",
                    border: `1px solid ${themeToken.colorBorder}`,
                    borderRadius: 12,
                    padding: "8px",
                    minWidth: 220,
                  },
                }}
                placement="bottomRight"
                trigger={["click"]}
              >
                <button
                  type="button"
                  aria-label="用户菜单"
                  style={{
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "4px 14px 4px 4px",
                    borderRadius: 22,
                    background: "transparent",
                    border: "none",
                    transition: "all 0.2s ease",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = "var(--menu-hover-bg)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = "transparent")
                  }
                >
                  <Avatar src={user?.avatar_url || defaultAvatar}
                    size={32}
                    style={{
                      background:
                        "linear-gradient(135deg, var(--color-primary-hover) 0%, var(--color-primary) 100%)",
                      fontSize: 13,
                      fontWeight: 600,
                      flexShrink: 0,
                    }}
                  >
                    {userDisplayName(user).charAt(0).toUpperCase() || "U"}
                  </Avatar>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      lineHeight: 1.2,
                      textAlign: "left",
                      minWidth: 0,
                    }}
                  >
                    <span
                      style={{
                        color: "var(--color-text)",
                        fontWeight: 600,
                        fontSize: 13,
                        fontFamily: "'DM Sans', sans-serif",
                        whiteSpace: "nowrap",
                        maxWidth: 140,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {userDisplayName(user) || "未登录"}
                    </span>
                    {userRoleText && (
                      <span
                        style={{
                          color: "var(--color-text-secondary)",
                          fontSize: 10,
                          whiteSpace: "nowrap",
                        }}
                      >
                        {userRoleText}
                      </span>
                    )}
                  </div>
                </button>
              </Dropdown>
            </div>
          </header>

          {/* 可滚动内容区 */}
          <main
            style={{
              flex: 1,
              minHeight: 0,
              overflowY: "auto",
              overflowX: "hidden",
              padding: 20,
            }}
          >
            <Outlet />
          </main>
          <Tour
            open={tourOpen}
            steps={tourSteps}
            onFinish={handleTourFinish}
          />
        </Layout>
      </Layout>
    </div>
  );
};

export default MainLayout;
