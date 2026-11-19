// 导航配置：单一数据源。Sidebar 遍历它渲染，新增/调整菜单只改这一处。
//
// 字段说明：
//   id          唯一标识
//   path        路由路径
//   name        显示名称
//   icon        Element Plus 图标组件名（在 Sidebar 里映射）
//   group       分组标题（折叠态隐藏）
//   availability  'live' = 已有真实功能可进入；'planned' = 规划中，点击进占位页
//   note        占位页说明文字（仅 planned 用）
//
// S1 阶段：只有 legacy 是真实可用的完整旧控制台；其余菜单先指向规划占位页。
// S2 起逐项把 availability 改为 live 并指向迁移后的真实页面。

export const navGroups = [
  {
    id: 'workspace',
    title: '工作台',
    items: [
      {
        id: 'overview',
        path: '/overview',
        name: 'Overview',
        icon: 'Odometer',
        availability: 'planned',
        note: '全局健康与闭环入口将在 S2 基于真实数据构建，当前尚无 Incident 模型。',
      },
      {
        id: 'incidents',
        path: '/incidents',
        name: 'Incidents',
        icon: 'Warning',
        availability: 'planned',
        note: '事件生命周期视图。第一阶段为过渡视图（基于执行记录与告警），不伪造事件数据。',
      },
    ],
  },
  {
    id: 'infrastructure',
    title: '基础设施',
    items: [
      {
        id: 'hosts',
        path: '/hosts',
        name: 'Hosts',
        icon: 'Monitor',
        availability: 'planned',
        note: '主机台账与远程终端将在 S2 从旧控制台迁移，功能保持不变。',
      },
      {
        id: 'workloads',
        path: '/workloads',
        name: 'Workloads',
        icon: 'Box',
        availability: 'planned',
        note: '工作负载监控尚未接入。当前平台仅采集主机级指标，容器/实例级数据需部署采集器。',
      },
    ],
  },
  {
    id: 'observability',
    title: '可观测性',
    items: [
      {
        id: 'metrics',
        path: '/metrics',
        name: 'Metrics',
        icon: 'TrendCharts',
        availability: 'planned',
        note: '指标查询将在 S2 从旧监控标签迁移。',
      },
      {
        id: 'alerts',
        path: '/alerts',
        name: 'Alerts',
        icon: 'Bell',
        availability: 'planned',
        note: '告警规则与事件查询将在 S2 从旧监控标签拆分迁移。',
      },
    ],
  },
  {
    id: 'automation',
    title: '自动化',
    items: [
      {
        id: 'runbooks',
        path: '/runbooks',
        name: 'Runbooks',
        icon: 'MagicStick',
        availability: 'planned',
        note: '剧本库（当前 3 条硬编码规则）将在后续阶段配置化。',
      },
      {
        id: 'executions',
        path: '/executions',
        name: 'Executions',
        icon: 'List',
        availability: 'planned',
        note: '执行记录将在 S2 从旧审计标签迁移。',
      },
      {
        id: 'audit',
        path: '/audit',
        name: 'Audit',
        icon: 'Document',
        availability: 'planned',
        note: '统一审计视角将在 S2 从旧审计标签拆出。',
      },
    ],
  },
]

// 底部固定区（不随菜单滚动，折叠态显示图标）
export const footerNav = [
  {
    id: 'legacy',
    path: '/legacy',
    name: '旧版控制台',
    icon: 'ArrowLeft',
    availability: 'live',
    note: 'V1 完整功能，S2 迁移完成前通过此入口访问。',
  },
  {
    id: 'settings',
    path: '/settings',
    name: 'Settings',
    icon: 'Setting',
    availability: 'planned',
    note: '系统设置将在后续阶段实现，凭据管理不因 UI 改造降低安全性。',
  },
]

export const allNavItems = [
  ...navGroups.flatMap((g) => g.items),
  ...footerNav,
]
