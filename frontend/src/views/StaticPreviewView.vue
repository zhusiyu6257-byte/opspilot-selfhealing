<script setup>
import { Bell, Box, Document, Monitor } from '@element-plus/icons-vue'
</script>

<template>
  <div class="static-preview">
    <section class="static-preview__hero">
      <div class="static-preview__eyebrow">D0 · Static Readonly Preview</div>
      <h1>OpsPilot 静态只读展示</h1>
      <p>
        这是给 GPT 浏览使用的只读界面。当前构建不连接后端，不展示业务数据，也不开放任何执行能力。
      </p>
      <div class="static-preview__tags">
        <el-tag size="small" effect="dark" round>后端未连接</el-tag>
        <el-tag size="small" type="warning" effect="dark" round>无模拟数据</el-tag>
        <el-tag size="small" type="info" effect="dark" round>只读展示</el-tag>
      </div>
    </section>

    <section class="static-preview__grid">
      <el-card class="static-card" shadow="never">
        <template #header>
          <div class="static-card__header">
            <el-icon><Monitor /></el-icon>
            <span>当前可见结构</span>
          </div>
        </template>
        <p>左侧导航展示 S1 阶段确定的信息架构：Overview、Incidents、Hosts、Workloads、Metrics、Alerts、Runbooks、Executions、Audit。</p>
        <p>这些入口用于说明产品结构，不代表对应业务页面已经实现。</p>
      </el-card>

      <el-card class="static-card" shadow="never">
        <template #header>
          <div class="static-card__header">
            <el-icon><Document /></el-icon>
            <span>真实状态说明</span>
          </div>
        </template>
        <p>S1 布局、路由、Sidebar、Topbar 已完成并通过构建验收。</p>
        <p>规划中的模块统一显示“尚未实现 · 无模拟数据”，不会用假指标制造已完成的感觉。</p>
      </el-card>

      <el-card class="static-card" shadow="never">
        <template #header>
          <div class="static-card__header">
            <el-icon><Box /></el-icon>
            <span>数据边界</span>
          </div>
        </template>
        <p>本页不展示主机数量、健康状态、执行成功率、告警数量、MTTR 等需要后端的数据。</p>
        <p>因为当前静态构建没有 API、没有数据库、没有 Prometheus 连接。</p>
      </el-card>

      <el-card class="static-card" shadow="never">
        <template #header>
          <div class="static-card__header">
            <el-icon><Bell /></el-icon>
            <span>操作边界</span>
          </div>
        </template>
        <p>静态版不提供旧控制台入口，不调用 <code>/api</code>，不调用 <code>/prometheus</code>。</p>
        <p>不开放 SSH 命令下发、主机变更、剧本执行等写操作。</p>
      </el-card>
    </section>

    <section class="static-preview__note">
      <strong>为什么没有实时数据？</strong>
      <span>
        静态页面像一本印好的说明书，适合展示结构；实时数据需要后端 API 在线。D0 明确不部署后端，所以这里不显示任何业务数据。
      </span>
    </section>
  </div>
</template>

<style scoped>
.static-preview {
  max-width: 1180px;
  margin: 0 auto;
  padding: 36px 28px 56px;
}

.static-preview__hero {
  padding: 32px;
  border: 1px solid var(--op-line);
  border-radius: 4px;
  background: var(--op-panel);
}

.static-preview__eyebrow {
  color: var(--op-accent);
  font-family: var(--op-font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  margin-bottom: 12px;
}

.static-preview h1 {
  margin: 0 0 14px;
  color: var(--op-text-strong);
  font-size: 28px;
  font-weight: 600;
}

.static-preview__hero p {
  max-width: 760px;
  margin: 0;
  color: var(--op-text);
  line-height: 1.8;
  font-size: 14px;
}

.static-preview__tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 20px;
}

.static-preview__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

.static-card {
  background: var(--op-panel);
  border: 1px solid var(--op-line);
}

.static-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--op-text-strong);
}

.static-card p {
  color: var(--op-text);
  font-size: 13px;
  line-height: 1.75;
  margin: 0 0 10px;
}

.static-card code {
  color: var(--op-accent);
  font-family: var(--op-font-mono);
}

.static-preview__note {
  margin-top: 18px;
  padding: 18px 20px;
  border-left: 3px solid var(--op-warn);
  background: var(--op-panel);
  color: var(--op-text-muted);
  line-height: 1.75;
  font-size: 13px;
}

.static-preview__note strong {
  color: var(--op-text-strong);
  margin-right: 8px;
}

@media (max-width: 860px) {
  .static-preview {
    padding: 24px 16px 40px;
  }

  .static-preview__grid {
    grid-template-columns: 1fr;
  }
}
</style>
