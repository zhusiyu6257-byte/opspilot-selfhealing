<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  ArrowLeft,
  Bell,
  Box,
  Document,
  List,
  MagicStick,
  Monitor,
  Odometer,
  Setting,
  TrendCharts,
  Warning,
} from '@element-plus/icons-vue'
import { useLayoutStore } from '@/stores/layout.js'
import { navGroups, footerNav } from '@/config/nav.js'
import { READONLY_LIVE, STATIC_READONLY } from '@/config/runtime.js'

const route = useRoute()
const layout = useLayoutStore()
const hideLegacyNav = computed(() => STATIC_READONLY || READONLY_LIVE)
const visibleFooterNav = computed(() =>
  hideLegacyNav.value ? footerNav.filter((item) => item.id !== 'legacy') : footerNav,
)
const brandSubtitle = computed(() => {
  if (STATIC_READONLY) return 'Static Readonly Preview'
  if (READONLY_LIVE) return 'Readonly Live'
  return 'Self-Healing Console'
})

const iconMap = {
  Odometer,
  Warning,
  Monitor,
  Box,
  TrendCharts,
  Bell,
  MagicStick,
  List,
  Document,
  ArrowLeft,
  Setting,
}

const collapsedClass = computed(() => ({
  'op-sidebar--collapsed': layout.collapsed,
}))

function iconFor(name) {
  return iconMap[name] || Document
}

function isActive(path) {
  return route.path === path || route.path.startsWith(`${path}/`)
}

function itemAvailability(item) {
  if (READONLY_LIVE && item.id === 'overview') return 'live'
  return item.availability
}

function itemClass(item) {
  return {
    'op-nav__item': true,
    'op-nav__item--active': isActive(item.path),
    'op-nav__item--planned': itemAvailability(item) === 'planned',
    'op-nav__item--collapsed': layout.collapsed,
  }
}
</script>

<template>
  <aside class="op-sidebar" :class="collapsedClass">
    <div class="op-sidebar__brand">
      <div class="op-sidebar__mark">
        <el-icon :size="18"><Monitor /></el-icon>
      </div>
      <div v-if="!layout.collapsed" class="op-sidebar__brand-text">
        <strong>OpsPilot</strong>
        <span>{{ brandSubtitle }}</span>
      </div>
    </div>

    <nav class="op-sidebar__nav" aria-label="主导航">
      <section v-for="group in navGroups" :key="group.id" class="op-nav-group">
        <div v-if="!layout.collapsed" class="op-nav-group__title">{{ group.title }}</div>
        <div v-else class="op-nav-group__divider"></div>

        <el-tooltip
          v-for="item in group.items"
          :key="item.id"
          :content="item.name"
          placement="right"
          :disabled="!layout.collapsed"
        >
          <router-link :to="item.path" :class="itemClass(item)">
            <span class="op-nav__icon">
              <el-icon :size="17"><component :is="iconFor(item.icon)" /></el-icon>
            </span>
            <span v-if="!layout.collapsed" class="op-nav__label">{{ item.name }}</span>
            <span
              v-if="!layout.collapsed && itemAvailability(item) === 'planned'"
              class="op-nav__flag"
            >规划</span>
          </router-link>
        </el-tooltip>
      </section>
    </nav>

    <div class="op-sidebar__footer">
      <el-tooltip
        v-for="item in visibleFooterNav"
        :key="item.id"
        :content="item.name"
        placement="right"
        :disabled="!layout.collapsed"
      >
        <router-link :to="item.path" :class="itemClass(item)">
          <span class="op-nav__icon">
            <el-icon :size="17"><component :is="iconFor(item.icon)" /></el-icon>
          </span>
          <span v-if="!layout.collapsed" class="op-nav__label">{{ item.name }}</span>
        </router-link>
      </el-tooltip>
    </div>
  </aside>
</template>

<style scoped>
.op-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 20;
  display: flex;
  flex-direction: column;
  width: var(--op-sidebar-w);
  background: var(--op-panel);
  border-right: 1px solid var(--op-line);
  transition: width var(--op-transition) ease;
  overflow: hidden;
}

.op-sidebar--collapsed {
  width: var(--op-sidebar-w-collapsed);
}

.op-sidebar__brand {
  height: var(--op-topbar-h);
  flex: 0 0 var(--op-topbar-h);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid var(--op-line);
}

.op-sidebar--collapsed .op-sidebar__brand {
  justify-content: center;
  padding: 0;
}

.op-sidebar__mark {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  color: var(--op-accent);
  background: var(--op-panel-2);
  border: 1px solid var(--op-line-strong);
  border-radius: 4px;
  flex: 0 0 auto;
}

.op-sidebar__brand-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.2;
}

.op-sidebar__brand-text strong {
  color: var(--op-text-strong);
  font-size: 14px;
  letter-spacing: 0.02em;
}

.op-sidebar__brand-text span {
  margin-top: 3px;
  color: var(--op-text-muted);
  font-size: 10px;
  white-space: nowrap;
}

.op-sidebar__nav {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px 10px;
}

.op-nav-group + .op-nav-group {
  margin-top: 14px;
}

.op-nav-group__title {
  padding: 0 10px 8px;
  color: var(--op-text-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.op-nav-group__divider {
  height: 1px;
  margin: 8px 12px;
  background: var(--op-line);
}

.op-nav__item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 38px;
  padding: 0 10px;
  margin-bottom: 3px;
  color: var(--op-text);
  text-decoration: none;
  border: 1px solid transparent;
  border-radius: 3px;
  transition: background var(--op-transition) ease, color var(--op-transition) ease,
    border-color var(--op-transition) ease;
}

.op-nav__item:hover {
  color: var(--op-text-strong);
  background: var(--op-panel-2);
}

.op-nav__item--active {
  color: var(--op-accent);
  background: color-mix(in srgb, var(--op-accent) 10%, transparent);
  border-color: color-mix(in srgb, var(--op-accent) 28%, transparent);
}

.op-nav__item--planned {
  color: var(--op-text-muted);
}

.op-nav__item--collapsed {
  justify-content: center;
  padding: 0;
}

.op-nav__icon {
  display: grid;
  place-items: center;
  width: 18px;
  flex: 0 0 18px;
}

.op-nav__label {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.op-nav__flag {
  margin-left: auto;
  color: var(--op-text-muted);
  font-size: 10px;
  border: 1px solid var(--op-line-strong);
  border-radius: 2px;
  padding: 1px 4px;
}

.op-sidebar__footer {
  flex: 0 0 auto;
  padding: 10px;
  border-top: 1px solid var(--op-line);
}

@media (max-width: 900px) {
  .op-sidebar {
    width: var(--op-sidebar-w-collapsed);
  }

  .op-sidebar__brand-text,
  .op-nav__label,
  .op-nav__flag,
  .op-nav-group__title {
    display: none;
  }

  .op-sidebar__brand,
  .op-nav__item--collapsed {
    justify-content: center;
    padding: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .op-sidebar,
  .op-nav__item {
    transition: none;
  }
}
</style>
