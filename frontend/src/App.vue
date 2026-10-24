<template>
  <!-- 1. 全屏安全认证/初始化层 (当且仅当 Docker 环境且未登录或未初始化时展示) -->
  <div v-if="authStatus.auth_required && (!authStatus.is_initialized || !authStatus.logged_in)" class="auth-fullscreen-container">
    <!-- 初始化界面：首次使用设置访问密码 -->
    <div v-if="!authStatus.is_initialized" class="auth-glass-card">
      <div class="auth-card-header">
        <div class="auth-badge-docker">
          <span class="live-dot-blue"></span>
          <span>Docker 容器运行环境</span>
        </div>
        <h2 class="auth-title">系统初始化设置</h2>
        <p class="auth-desc">
          检测到服务运行在 Docker 容器中。为防止公开端口未授权访问并保护您的节点与母本配置安全，请先设置系统访问密码。
        </p>
      </div>

      <el-form class="auth-form" label-position="top" @submit.prevent="handleInitPassword">
        <el-form-item label="设置访问密码">
          <el-input
            v-model="initPasswordForm.password"
            type="password"
            show-password
            placeholder="请输入管理员访问密码 (至少4位)"
            size="large"
            autofocus
          >
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item label="确认访问密码">
          <el-input
            v-model="initPasswordForm.confirm_password"
            type="password"
            show-password
            placeholder="请再次输入以确认密码"
            size="large"
            @keyup.enter="handleInitPassword"
          >
            <template #prefix><el-icon><Check /></el-icon></template>
          </el-input>
        </el-form-item>

        <div v-if="authErrorMessage" class="auth-error-banner">
          {{ authErrorMessage }}
        </div>

        <button
          type="button"
          class="auth-submit-btn"
          :disabled="submittingAuth || !initPasswordForm.password || !initPasswordForm.confirm_password"
          @click="handleInitPassword"
        >
          <el-icon v-if="submittingAuth" class="is-loading"><Loading /></el-icon>
          <span>{{ submittingAuth ? '正在保存初始化设置...' : '完成初始化并进入系统' }}</span>
        </button>

        <div class="auth-footer-tip">
          <span class="tip-dot">•</span>
          <span>设置后密码将持久化保存在数据目录 (auth.json) 中，后续重启或更新容器保持生效。</span>
        </div>
      </el-form>
    </div>

    <!-- 登录界面：已初始化但尚未登录 -->
    <div v-else class="auth-glass-card">
      <div class="auth-card-header">
        <div class="auth-badge-docker">
          <span class="live-dot-green"></span>
          <span>安全保护已就绪</span>
        </div>
        <h2 class="auth-title">YmlManage 控制台</h2>
        <p class="auth-desc">
          已启用 Docker 容器安全防护，请输入访问密码以解锁控制面板。
        </p>
      </div>

      <el-form class="auth-form" label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="访问密码">
          <el-input
            v-model="loginPassword"
            type="password"
            show-password
            placeholder="请输入访问密码"
            size="large"
            autofocus
            @keyup.enter="handleLogin"
          >
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>

        <div v-if="authErrorMessage" class="auth-error-banner">
          {{ authErrorMessage }}
        </div>

        <button
          type="button"
          class="auth-submit-btn"
          :disabled="submittingAuth || !loginPassword"
          @click="handleLogin"
        >
          <el-icon v-if="submittingAuth" class="is-loading"><Loading /></el-icon>
          <span>{{ submittingAuth ? '身份验证中...' : '验证并进入控制台' }}</span>
        </button>

        <div class="auth-footer-tip">
          <span class="tip-dot">•</span>
          <span>若忘记密码，可在宿主机挂载的 data/auth.json 中重置或删除。</span>
        </div>
      </el-form>
    </div>
  </div>

  <!-- 2. 主系统界面 (本地免密环境 或 Docker环境已认证) -->
  <div v-else class="xui-app-container">
    <!-- 顶部导航栏 (已删除左上角 3X 徽标，呼吸感拉开) -->
    <header class="xui-top-header">
      <div class="header-brand-section">
        <div class="status-pill-3x">
          <span class="status-live-dot"></span>
          <span class="status-tip-text">母本已载入:</span>
          <span class="status-name-text">{{ currentProfile }}</span>
        </div>

        <div class="profile-select-inline">
          <span class="inline-label">切换母本:</span>
          <el-select
            v-model="currentProfile"
            placeholder="请选择母本"
            size="small"
            style="width: 220px"
            @change="handleProfileChange"
          >
            <el-option
              v-for="p in profileList"
              :key="p.name"
              :label="p.name"
              :value="p.name"
            >
              <div class="select-row-flex">
                <span>{{ p.name }}</span>
                <span class="select-sub-info">({{ p.group_count }} 策略组)</span>
              </div>
            </el-option>
          </el-select>
        </div>
      </div>

      <!-- 右侧操作栏 (母本管理与常用源) -->
      <div class="header-action-section">
        <div
          v-if="systemInfo.lan_ip && systemInfo.lan_ip !== '127.0.0.1'"
          class="lan-pill-btn"
          @click="copyLanUrl"
          :title="'点击复制局域网访问地址: ' + systemInfo.lan_url"
        >
          <span class="lan-live-dot"></span>
          <span class="lan-text">局域网: {{ systemInfo.lan_ip }}:{{ systemInfo.port }}</span>
        </div>
        <div class="header-nav-btns-row">
          <button class="xui-nav-btn" @click="openRemoteUploadDialog(currentProfile)" title="将当前编辑好的母本上传至指定设备 (SMB/FTP/WebDAV)">
            <el-icon><Upload /></el-icon>
            <span>上传至远程</span>
          </button>
          <button class="xui-nav-btn" @click="openProfileModal">
            <el-icon><Folder /></el-icon>
            <span>母本管理</span>
          </button>
          <button class="xui-nav-btn" @click="openSourceModal">
            <el-icon><Collection /></el-icon>
            <span>常用订阅源</span>
          </button>
          <template v-if="authStatus.auth_required">
            <button class="xui-nav-btn" @click="openChangePasswordDialog" title="修改 Docker 网页访问密码">
              <el-icon><Key /></el-icon>
              <span>修改密码</span>
            </button>
            <button class="xui-nav-btn danger-hover" @click="handleLogout" title="退出当前登录">
              <el-icon><SwitchButton /></el-icon>
              <span>退出</span>
            </button>
          </template>
        </div>
      </div>
    </header>

    <!-- 主工作区 (间距充裕，告别上下拥挤) -->
    <main class="xui-main-content">
      <!-- 订阅提取控制面板 (3X-UI 宽屏舒展卡片) -->
      <section class="xui-card-panel">
        <div class="panel-head-bar">
          <div class="panel-head-title-flex">
            <span class="panel-head-title">提取外部订阅节点并进行 URL Test 延迟测试</span>
          </div>

          <div class="panel-head-right" style="display: flex; align-items: center; gap: 16px;">
            <div class="test-url-selector-wrap" style="display: flex; align-items: center;">
              <span class="quick-src-label">URL Test 接口:</span>
              <el-select
                v-model="activeTestUrl"
                placeholder="选取 URL Test 接口"
                size="small"
                style="width: 220px"
                @change="handleTestUrlChange"
              >
                <el-option
                  v-for="item in testUrlsList"
                  :key="item.url"
                  :label="item.name"
                  :value="item.url"
                >
                  <div class="test-url-option">
                    <span class="opt-name">{{ item.name }}</span>
                    <span class="opt-desc">{{ item.desc }}</span>
                  </div>
                </el-option>
              </el-select>
            </div>

            <div class="quick-source-wrap" style="display: flex; align-items: center;" v-if="savedSources.length > 0">
              <span class="quick-src-label">载入常用源:</span>
              <el-select
                v-model="selectedSourceId"
                placeholder="快速载入常用源"
                size="small"
                style="width: 170px"
                @change="applyQuickSource"
                clearable
              >
                <el-option
                  v-for="s in savedSources"
                  :key="s.id"
                  :label="s.name"
                  :value="s.id"
                />
              </el-select>
            </div>
          </div>
        </div>

        <div class="panel-inner-body">
          <div class="fetch-action-bar">
            <div class="fetch-input-field">
              <el-input
                v-model="fetchUrl"
                placeholder="请输入外部订阅链接 (支持 Clash YAML、Base64 或单节点链接)"
                clearable
                @keyup.enter="handleFetchNodes"
              >
                <template #prefix>
                  <el-icon color="#8b949e"><Link /></el-icon>
                </template>
              </el-input>
            </div>

            <button class="xui-std-btn" @click="pasteFromClipboard" title="从剪贴板读取">
              <el-icon><DocumentCopy /></el-icon>
              <span>粘贴</span>
            </button>

            <button
              class="xui-primary-btn"
              :disabled="fetching"
              @click="handleFetchNodes"
            >
              <el-icon :class="{ 'is-loading': fetching }"><Search /></el-icon>
              <span>{{ fetching ? 'URL Testing...' : '提取并测试' }}</span>
            </button>
          </div>

          <div class="panel-note-line" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span class="note-dot" :style="{ background: isDomesticTestUrl ? '#f59e0b' : '#38bdf8' }"></span>
              <span v-if="isDomesticTestUrl" style="color: #f59e0b; font-weight: 500;">
                提示：当前选取了国内直连接口，海外节点访问属于【出海再回国】线路，延迟通常偏高(400~1000ms+)。建议切换为 Cloudflare 204 或 Google 204 测出海外节点真实物理延迟。
              </span>
              <span v-else>
                内置 Mihomo 官方内核（已开启 Unified Delay 真实延迟算法）与 DoH 直连公网探测真实 RTT 握手延时，消除 TLS 握手干扰，精准识别死节点。
              </span>
            </div>
            <div class="filter-switch-wrap">
              <el-checkbox v-model="filterDeadOption" label="自动剔除超时/失效节点" size="small" />
            </div>
          </div>
        </div>
      </section>

      <!-- 整体左右布局：左侧四张指标卡片，右侧【有效节点卡片池】 -->
      <div class="xui-workspace-split" :class="{ 'is-empty-nodes': !hasFetched || filteredNodes.length === 0 }">
        <!-- 左侧：四张指标卡片 -->
        <aside class="xui-metrics-sidebar" :class="{ 'is-empty-nodes': !hasFetched || filteredNodes.length === 0 }">
          <div
            class="xui-metric-box clickable-metric"
            @click="handleOpenCurrentProfileGroups"
            title="点击进入当前母本的策略组管理"
          >
            <div class="metric-top">
              <span class="m-title">当前母本</span>
              <el-icon color="#58a6ff"><Files /></el-icon>
            </div>
            <div class="m-val">{{ currentGroups.length }} <span class="m-unit">策略组</span></div>
            <div class="m-sub">母本当前包含 {{ currentProxyCount }} 个节点</div>
          </div>

          <div class="xui-metric-box">
            <div class="metric-top">
              <span class="m-title">本次提取</span>
              <el-icon color="#a5b4fc"><Download /></el-icon>
            </div>
            <div class="m-val">{{ totalRawCount }} <span class="m-unit">个原始节点</span></div>
            <div class="m-sub" v-if="filteredCount > 0" style="color: #f87171;">
              已自动过滤 {{ filteredCount }} 个失效/广告
            </div>
            <div class="m-sub" v-else>等待输入订阅链接</div>
          </div>

          <div class="xui-metric-box">
            <div class="metric-top">
              <span class="m-title">有效可用</span>
              <el-icon color="#3fb950"><CircleCheck /></el-icon>
            </div>
            <div class="m-val text-green">{{ fetchedNodes.length }} <span class="m-unit">可用</span></div>
            <div class="m-sub">经 NekoBox 同款 URL Test 验证存活</div>
          </div>

          <div
            class="xui-metric-box"
            :class="{ 'clickable-metric': selectedNodeIds.length > 0 }"
            @click="selectedNodeIds.length > 0 && openImportDrawer()"
            title="点击打开导入配置抽屉"
          >
            <div class="metric-top">
              <span class="m-title">已勾选待导入</span>
              <el-icon color="#79c0ff"><Upload /></el-icon>
            </div>
            <div class="m-val text-blue">{{ selectedNodeIds.length }} <span class="m-unit">个节点</span></div>
            <div class="m-sub">{{ selectedNodeIds.length > 0 ? '点击打开导入配置抽屉' : '可一键批量导入指定策略组' }}</div>
          </div>
        </aside>

        <!-- 右侧：【有效节点卡片池】 (或初始空白引导) -->
        <div class="xui-pool-main" :class="{ 'is-empty-nodes': !hasFetched || filteredNodes.length === 0 }">
      <!-- 节点卡片池 (优雅沉稳的选中配色，完美融入主题) -->
      <section class="xui-card-panel" v-if="hasFetched">
        <div class="panel-head-bar">
          <div class="panel-head-title-flex">
            <span>有效节点卡片池</span>
            <span class="panel-num-pill">{{ filteredNodes.length }}</span>


          </div>

          <div class="panel-head-actions">
            <!-- 排序切换按钮组 (延迟优先 / 默认顺序) -->
            <div class="xui-mini-btn-group">
              <button
                class="m-btn"
                :class="{ 'm-btn-active': sortMode === 'delay' }"
                @click="setSortMode('delay')"
                title="延迟优先：按 URL Test 延迟由低到高排序"
              >延迟优先</button>
              <button
                class="m-btn"
                :class="{ 'm-btn-active': sortMode === 'default' }"
                @click="setSortMode('default')"
                title="默认排序：保持订阅原始顺序"
              >默认顺序</button>
            </div>

            <el-input
              v-model="searchKeyword"
              placeholder="搜索节点或协议..."
              size="small"
              clearable
              style="width: 210px;"
            >
              <template #prefix>
                <el-icon color="#8b949e"><Search /></el-icon>
              </template>
            </el-input>

            <div class="xui-mini-btn-group">
              <button class="m-btn" @click="selectAll">全选</button>
              <button class="m-btn" @click="selectNone">取消</button>
              <button class="m-btn m-btn-highlight" @click="selectOnlyNew">仅选新节点</button>
            </div>

            <button
              class="xui-primary-btn"
              :disabled="selectedNodeIds.length === 0"
              @click="openImportDrawer"
            >
              <el-icon><Upload /></el-icon>
              <span>导入所选 ({{ selectedNodeIds.length }})</span>
            </button>
          </div>
        </div>

        <div class="panel-inner-body">
          <!-- 3X-UI 高质感节点卡片网格 -->
          <div class="xui-nodes-grid">
            <div
              v-for="node in filteredNodes"
              :key="node.id"
              class="xui-node-card"
              :class="{
                'card-selected': isNodeSelected(node.id),
                'card-existing': node.is_existing
              }"
              @click="toggleNodeSelection(node.id)"
            >
              <!-- 顶部：左上角纯国旗 + 节点名称(超长省略+Tooltip) + 状态 + 复选指示器 -->
              <div class="node-card-top-line">
                <div class="node-title-wrapper">
                  <!-- 左上角国旗 (无外层矩形底色/边框) -->
                  <span
                    v-if="getNodeLocation(node, ipLocationMap).code !== 'UN'"
                    class="node-card-flag"
                    :title="getNodeLocation(node, ipLocationMap).fullText"
                  >
                    <span
                      v-if="getNodeLocation(node, ipLocationMap).svg"
                      class="country-flag-svg"
                      v-html="getNodeLocation(node, ipLocationMap).svg"
                    ></span>
                    <span v-else class="loc-flag">{{ getNodeLocation(node, ipLocationMap).flag }}</span>
                  </span>

                  <!-- 节点名称超出省略号 + Tooltip 浮窗提示 -->
                  <el-tooltip
                    :content="node.name"
                    placement="top"
                    :show-after="300"
                    :enterable="false"
                  >
                    <span class="node-title-main">
                      {{ node.name }}
                    </span>
                  </el-tooltip>
                </div>

                <div class="card-top-right">
                  <span v-if="node.is_existing" class="tag-in-master">
                    已存在
                  </span>
                  <!-- 未选中不显示，选中仅在右上角显示圆形里面一个√ -->
                  <div v-if="isNodeSelected(node.id)" class="circle-check-badge">
                    <el-icon :size="10"><Check /></el-icon>
                  </div>
                </div>
              </div>

              <!-- 底部：协议类型 + [延迟标记] -->
              <div class="node-card-bottom-line">
                <span class="node-proto-label" :title="node.proto_display || node.type">{{ node.proto_display || node.type }}</span>

                <div class="node-metrics-tags">
                  <!-- URL Test 真实延迟标记 (NekoBox 同款) -->
                  <span
                    class="node-delay-pill"
                    :class="getDelayClass(node.delay)"
                  >
                    {{ node.delay > 0 ? `${node.delay} ms` : '超时' }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="filteredNodes.length === 0" class="filter-empty-tip">
            没有符合搜索条件的节点
          </div>
        </div>
      </section>

      <!-- 初始空白引导 -->
      <div v-else class="xui-empty-guide">
        <div class="guide-circle-icon">
          <el-icon :size="26" color="#58a6ff"><Connection /></el-icon>
        </div>
        <h3 class="guide-title">等待提取节点</h3>
        <p class="guide-desc">粘贴外部订阅链接并点击「提取节点」，系统将自动执行 URL Test 探测延迟并精准剔除死节点</p>
      </div>
        </div>
      </div>
    </main>

    <!-- 导入策略组抽屉 (完全 3X-UI 暗黑定制) -->
    <el-drawer
      v-model="importDrawerVisible"
      title="配置导入目标策略组"
      direction="rtl"
      size="480px"
      class="xui-custom-drawer"
    >
      <div class="drawer-layout-body">
        <div class="drawer-target-card">
          <span class="target-title">目标母本：<strong>{{ currentProfile }}</strong></span>
          <span class="target-num">准备导入 {{ selectedNodeIds.length }} 个节点</span>
        </div>

        <div class="drawer-form-section">
          <div class="section-header-row">
            <span>1. 勾选要注入的策略组 (proxy-groups)</span>
            <div class="header-fast-links">
              <button class="fast-link" @click="selectAllGroups">全选</button>
              <button class="fast-link" @click="clearAllGroups">清空</button>
            </div>
          </div>

          <div class="groups-select-scroll">
            <div v-if="currentGroups.length === 0" class="muted-text">
              母本未定义策略组，导入节点将保存在 proxies 列表中。
            </div>
            <el-checkbox-group v-model="selectedGroupNames" class="checkbox-col-stack">
              <div
                v-for="g in currentGroups"
                :key="g.name"
                class="group-row-item"
              >
                <el-checkbox :label="g.name" :value="g.name">
                  <span class="g-name-text">{{ g.name }}</span>
                  <span class="g-type-text">({{ g.type }})</span>
                </el-checkbox>
              </div>
            </el-checkbox-group>
          </div>
        </div>

        <div class="drawer-form-section">
          <div class="section-header-row">2. 同名节点处理策略</div>
          <el-radio-group v-model="overwriteOption" class="radio-vertical-stack">
            <el-radio :value="true">
              <span class="radio-main-txt">覆盖更新现有节点 (推荐)</span>
              <span class="radio-sub-txt">母本中已有同名节点时，更新其服务器/密钥等数据</span>
            </el-radio>
            <el-radio :value="false">
              <span class="radio-main-txt">跳过已存在节点</span>
              <span class="radio-sub-txt">仅导入母本中不存在的全新节点</span>
            </el-radio>
          </el-radio-group>
        </div>

        <div class="drawer-form-section">
          <div class="section-header-row">3. 安全快照备份</div>
          <div class="safe-callout-card">
            执行写入前，系统会自动在本地 <code>data/backups/</code> 生成带时间戳的快照副本。
          </div>
        </div>

        <div class="drawer-footer-row">
          <button class="xui-std-btn" @click="importDrawerVisible = false">取消</button>
          <button class="xui-primary-btn" :disabled="importing" @click="confirmImport">
            <el-icon v-if="importing" class="is-loading"><Loading /></el-icon>
            <span>{{ importing ? '写入中...' : '确认执行导入' }}</span>
          </button>
        </div>
      </div>
    </el-drawer>

    <!-- 母本管理弹窗 (完全 3X-UI 暗黑定制，消除割裂感) -->
    <el-dialog
      v-model="profileModalVisible"
      title="母本管理中心"
      width="960px"
      class="xui-custom-dialog"
    >
      <el-tabs v-model="profileActiveTab" class="xui-custom-tabs">
        <el-tab-pane label="母本列表" name="list">
          <!-- 桌面端表格 (大屏宽屏展示) -->
          <el-table :data="profileList" style="width: 100%" class="xui-custom-table desktop-only-table" stripe>
            <el-table-column prop="name" label="母本文件名" min-width="170">
              <template #default="{ row }">
                <span class="tbl-name-label" :class="{ 'is-active': row.name === currentProfile }">
                  {{ row.name }}
                  <span v-if="row.name === currentProfile" class="curr-badge">当前</span>
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="proxy_count" label="节点数" width="80" align="center" />
            <el-table-column prop="group_count" label="策略组数" width="90" align="center" />
            <el-table-column prop="updated_at" label="最后修改" width="170" align="center" />
            <el-table-column label="操作" width="340" align="right">
              <template #default="{ row }">
                <div class="row-actions-flex">
                  <el-button size="small" type="primary" link @click="switchProfile(row.name)">切换</el-button>
                  <el-button size="small" type="primary" link @click="openProfileEditor(row.name)">编辑</el-button>
                  <el-button size="small" link @click="openBackups(row.name)">快照({{ row.backup_count }})</el-button>
                  <el-button size="small" type="success" link @click="openRemoteUploadDialog(row.name)" title="上传到指定路径 (SMB/FTP/WebDAV)">上传</el-button>
                  <el-popconfirm title="确认删除此母本文件吗？" @confirm="handleDeleteProfile(row.name)">
                    <template #reference>
                      <el-button size="small" type="danger" link>删除</el-button>
                    </template>
                  </el-popconfirm>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <!-- 手机端卡片列表 (零横向滚动，高亮【编辑】直接触达) -->
          <div class="mobile-only-cards profile-mobile-card-list">
            <div
              v-for="row in profileList"
              :key="row.name"
              class="profile-m-item"
              :class="{ 'is-current': row.name === currentProfile }"
            >
              <div class="pmi-head">
                <div class="pmi-title">
                  <span class="pmi-name">{{ row.name }}</span>
                  <span v-if="row.name === currentProfile" class="curr-badge">当前</span>
                </div>
                <div class="pmi-meta-tags">
                  <span class="pmi-tag">{{ row.proxy_count }} 节点</span>
                  <span class="pmi-tag">{{ row.group_count }} 策略组</span>
                </div>
              </div>

              <div class="pmi-time-row">
                <span class="pmi-time-label">修改时间: {{ row.updated_at || '刚刚' }}</span>
              </div>

              <div class="pmi-actions-row">
                <button class="pmi-btn pmi-btn-edit" @click="openProfileEditor(row.name)">
                  <el-icon><Edit /></el-icon>
                  <span>编辑</span>
                </button>
                <button
                  class="pmi-btn pmi-btn-switch"
                  :class="{ active: row.name === currentProfile }"
                  :disabled="row.name === currentProfile"
                  @click="switchProfile(row.name)"
                >
                  <el-icon><Check /></el-icon>
                  <span>{{ row.name === currentProfile ? '已载入' : '切换' }}</span>
                </button>
                <button class="pmi-btn pmi-btn-sub" @click="openBackups(row.name)">
                  <el-icon><DocumentCopy /></el-icon>
                  <span>快照({{ row.backup_count }})</span>
                </button>
                <button class="pmi-btn pmi-btn-sub" @click="openRemoteUploadDialog(row.name)" title="上传到远程路径">
                  <el-icon><Upload /></el-icon>
                  <span>上传</span>
                </button>
                <el-popconfirm title="确认删除此母本文件吗？" @confirm="handleDeleteProfile(row.name)">
                  <template #reference>
                    <button class="pmi-btn pmi-btn-danger">
                      <el-icon><Delete /></el-icon>
                      <span>删除</span>
                    </button>
                  </template>
                </el-popconfirm>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="从链接下载母本" name="download">
          <el-form label-position="top">
            <el-form-item label="订阅链接 (必须返回合规 Clash YAML，系统将自动读取识别文件名)">
              <el-input v-model="newProfileUrl" placeholder="https://..." clearable />
            </el-form-item>
            <div style="margin-top: 14px;">
              <button class="xui-primary-btn" :disabled="downloadingProfile || !newProfileUrl.trim()" @click="handleDownloadProfile">
                {{ downloadingProfile ? '下载识别中...' : '下载并保存为母本' }}
              </button>
            </div>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="上传本地 YAML" name="upload">
          <el-upload
            class="upload-3x-panel"
            drag
            action="#"
            :auto-upload="false"
            :on-change="handleFileChange"
            :limit="1"
            accept=".yaml,.yml"
          >
            <el-icon :size="36" color="#8b949e"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽母本 YAML 到此处，或 <em>点击上传</em></div>
          </el-upload>
          <div style="margin-top: 14px;">
            <button class="xui-primary-btn" :disabled="!uploadedFile || uploadingProfile" @click="handleUploadProfile">
              {{ uploadingProfile ? '上传处理中...' : '确认上传为母本' }}
            </button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="基于模板新建" name="template">
          <p class="muted-text" style="margin-bottom: 12px;">
            基于项目根目录【母本模板.yml】模板，复制生成一份新的母本配置：
          </p>
          <div style="display: flex; gap: 10px;">
            <el-input v-model="templateProfileName" placeholder="新母本名称，如 自定义分流" style="width: 260px;" />
            <button class="xui-primary-btn" @click="handleCreateDefaultTemplate">立即创建</button>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <!-- 常用源管理弹窗 (完全 3X-UI 暗黑定制) -->
    <el-dialog
      v-model="sourceModalVisible"
      title="常用订阅源管理"
      width="960px"
      class="xui-custom-dialog"
    >
      <div style="margin-bottom: 14px; display: flex; justify-content: flex-end;">
        <button class="xui-primary-btn" @click="openAddSourceDialog">
          <el-icon><Plus /></el-icon>
          <span>添加新订阅源</span>
        </button>
      </div>
      <!-- 桌面端表格 -->
      <el-table :data="savedSources" style="width: 100%" class="xui-custom-table desktop-only-table" stripe>
        <el-table-column prop="name" label="名称" width="160" />
        <el-table-column prop="url" label="订阅链接" min-width="480" show-overflow-tooltip />
        <el-table-column prop="notes" label="备注" width="110" show-overflow-tooltip />
        <el-table-column label="操作" width="130" align="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="openEditSourceDialog(row)">编辑</el-button>
            <el-popconfirm title="确定删除此源？" @confirm="handleDeleteSource(row.id)">
              <template #reference>
                <el-button size="small" type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 手机端卡片列表 -->
      <div class="mobile-only-cards source-mobile-card-list">
        <div v-for="row in savedSources" :key="row.id" class="source-m-item">
          <div class="smi-head">
            <span class="smi-name">{{ row.name }}</span>
            <span v-if="row.notes" class="smi-notes">{{ row.notes }}</span>
          </div>
          <div class="smi-url">{{ row.url }}</div>
          <div class="smi-actions">
            <button class="pmi-btn" @click="openEditSourceDialog(row)">
              <el-icon><Edit /></el-icon>
              <span>编辑</span>
            </button>
            <el-popconfirm title="确定删除此源？" @confirm="handleDeleteSource(row.id)">
              <template #reference>
                <button class="pmi-btn pmi-btn-danger">
                  <el-icon><Delete /></el-icon>
                  <span>删除</span>
                </button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 添加 / 编辑常用源弹窗 -->
    <el-dialog
      v-model="addSourceDialogVisible"
      :title="editingSourceId ? '编辑常用订阅源' : '添加常用订阅源'"
      width="480px"
      class="xui-custom-dialog"
    >
      <el-form label-position="top">
        <el-form-item label="订阅源名称 (如: 主力机场)">
          <el-input v-model="sourceForm.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="订阅链接">
          <el-input v-model="sourceForm.url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="备注说明 (可选)">
          <el-input v-model="sourceForm.notes" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <button class="xui-std-btn" @click="addSourceDialogVisible = false">取消</button>
        <button class="xui-primary-btn" style="margin-left: 8px;" @click="handleSaveSource">
          {{ editingSourceId ? '保存修改' : '保存' }}
        </button>
      </template>
    </el-dialog>

    <!-- 母本可视化编辑与源码编辑弹窗 (完全 3X-UI 暗黑科技定制) -->
    <el-dialog
      v-model="profileEditorVisible"
      :title="`母本编辑: ${editorProfileName}`"
      width="1280px"
      top="2.5vh"
      class="xui-custom-dialog xui-editor-dialog"
      :destroy-on-close="true"
    >
      <div v-loading="loadingEditorData" class="editor-main-container">
        <!-- 顶部主标签栏 (大间距、清晰层级) -->
        <div class="editor-tabs-bar">
          <div class="editor-segmented-tabs">
            <button
              class="editor-tab-btn"
              :class="{ active: editorActiveTab === 'groups' }"
              @click="switchEditorTab('groups')"
            >
              <el-icon><Files /></el-icon>
              <span>策略组管理</span>
              <span class="tab-count-badge">{{ editorGroups.length }}</span>
            </button>
            <button
              class="editor-tab-btn"
              :class="{ active: editorActiveTab === 'proxies' }"
              @click="switchEditorTab('proxies')"
            >
              <el-icon><Connection /></el-icon>
              <span>节点列表</span>
              <span class="tab-count-badge">{{ editorProxies.length }}</span>
            </button>
            <button
              class="editor-tab-btn"
              :class="{ active: editorActiveTab === 'yaml' }"
              @click="switchEditorTab('yaml')"
            >
              <el-icon><DocumentCopy /></el-icon>
              <span>YAML 源码</span>
            </button>
          </div>

          <div class="editor-meta-pill-group">
            <span v-if="editorRulesCount > 0" class="editor-meta-pill">
              <el-icon style="margin-right: 4px;"><DocumentCopy /></el-icon>
              {{ editorRulesCount }} 条分流规则
            </span>
          </div>
        </div>

        <!-- 1. 策略组管理 (Zashboard 双列卡片网格布局，支持拖拽排序与增删节点) -->
        <div v-if="editorActiveTab === 'groups'" class="editor-tab-content-pane">
          <!-- 策略组工具栏 -->
          <div class="editor-toolbar-row">
            <div class="editor-toolbar-left">
              <el-input
                v-model="groupSearchQuery"
                placeholder="搜索策略组名称或类型..."
                size="small"
                style="width: 320px;"
                clearable
              >
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
              <span class="tb-count-text">共 {{ filteredEditorGroups.length }} / {{ editorGroups.length }} 个策略组</span>
            </div>
            <div class="editor-toolbar-right">
              <button class="xui-primary-btn btn-sm" @click="openAddGroupDialog">
                <el-icon><Plus /></el-icon>
                <span>新建策略组</span>
              </button>
            </div>
          </div>

          <!-- Zashboard 风格 2 列策略组卡片网格 (支持拖拽滚动条自动滚动 & 鼠标滚轮滚动) -->
          <div
            ref="groupsGridRef"
            class="zashboard-groups-grid"
            @dragover="handleGroupsGridDragOver"
            @drop="handleGroupsGridDrop"
            @wheel="handleDragWheel"
          >
            <div
              v-for="(grp, gIdx) in filteredEditorGroups"
              :key="grp.name + '_' + gIdx"
              :data-group-index="gIdx"
              class="z-group-card"
              :class="{
                'is-card-dragging': dragGroupCardIdx === gIdx,
                'is-card-drop-target': dropTargetGroupCardIdx === gIdx
              }"
              draggable="true"
              @dragstart="handleGroupCardDragStart($event, gIdx)"
              @dragover="handleGroupCardDragOver($event, gIdx)"
              @dragleave="handleGroupCardDragLeave"
              @drop.stop="handleGroupCardDrop($event, gIdx)"
              @dragend="handleGroupCardDragEnd"
              @wheel="handleDragWheel"
            >
              <!-- 策略组卡片顶部 -->
              <div class="z-card-header">
                <div class="z-header-left">
                  <span class="z-card-drag-handle" title="按住拖拽调整策略组卡片顺序">⠿</span>
                  <span class="z-group-name" :title="grp.name">{{ grp.name }}</span>
                  <span class="z-type-pill" :class="'type-' + (grp.type || 'select')">{{ grp.type || 'select' }}</span>
                  <span class="z-node-count-badge">{{ (grp.proxies || []).length }} 节点</span>
                </div>
                <div class="z-header-actions">
                  <button class="z-action-btn primary" title="添加节点至此组" @click="openAddNodesToGroup(grp)">
                    <el-icon><Plus /></el-icon>
                    <span>添加节点</span>
                  </button>
                  <button class="z-action-btn" title="编辑策略组参数" @click="openEditGroupModal(grp)">
                    <el-icon><Edit /></el-icon>
                  </button>
                  <el-popconfirm
                    :title="`确定删除策略组「${grp.name}」？`"
                    @confirm="handleDeleteGroup(grp.name)"
                  >
                    <template #reference>
                      <button class="z-action-btn danger" title="删除策略组">
                        <el-icon><Delete /></el-icon>
                      </button>
                    </template>
                  </el-popconfirm>
                </div>
              </div>

              <!-- 自动测速/故障转移参数栏 -->
              <div v-if="grp.type !== 'select'" class="z-card-submeta">
                <span class="z-meta-item" :title="grp.url || '默认测速URL'">
                  <el-icon><Connection /></el-icon> {{ grp.url || '默认测速URL' }}
                </span>
                <span class="z-meta-item">
                  {{ grp.interval || 300 }}s / 容差 {{ grp.tolerance || 50 }}ms
                </span>
              </div>

              <!-- 组内节点卡片 (拖拽排序 + 删除 + 快速添加) -->
              <div
                class="z-card-chips-container"
                @dragover.prevent
                @drop="handleGroupContainerDrop($event, grp, gIdx)"
              >
                <div
                  v-for="(pName, pIdx) in grp.proxies"
                  :key="pName + '_' + pIdx"
                  class="z-node-chip"
                  :class="{
                    'is-dragging': dragGroupIndex === gIdx && dragNodeIndex === pIdx,
                    'is-drop-target': dragGroupIndex === gIdx && dropTargetNodeIndex === pIdx
                  }"
                  draggable="true"
                  @dragstart="handleGroupNodeDragStart($event, gIdx, pIdx)"
                  @dragover.prevent="handleGroupNodeDragOver($event, gIdx, pIdx)"
                  @dragleave="handleGroupNodeDragLeave($event)"
                  @drop.stop="handleGroupNodeDrop($event, gIdx, pIdx)"
                  @dragend="handleGroupNodeDragEnd"
                >
                  <span class="z-drag-handle" title="按住拖拽调整顺序">⠿</span>
                  <span class="z-proto-tag" :class="'proto-' + getMemberType(pName)">
                    {{ getMemberType(pName) }}
                  </span>
                  <span class="z-chip-name" :title="pName">{{ pName }}</span>
                  <button
                    class="z-chip-del-btn"
                    title="从本组移出"
                    @click.stop="removeNodeFromGroup(grp, pIdx)"
                  >
                    ×
                  </button>
                </div>

                <!-- 组内尾部「+ 添加节点」虚线按钮 -->
                <button class="z-add-chip-btn" @click="openAddNodesToGroup(grp)">
                  <el-icon><Plus /></el-icon>
                  <span>添加节点</span>
                </button>

                <div v-if="!grp.proxies || grp.proxies.length === 0" class="z-empty-group-tip">
                  当前策略组暂无节点，点击上方「添加节点」加入
                </div>
              </div>
            </div>
            <div v-if="filteredEditorGroups.length === 0" class="editor-empty-tip">
              未找到匹配的策略组
            </div>
          </div>
        </div>

        <!-- 2. 节点列表 (卡片形式展示) -->
        <div v-else-if="editorActiveTab === 'proxies'" class="editor-tab-content-pane">
          <!-- 节点工具栏 -->
          <div class="editor-toolbar-row">
            <div class="editor-toolbar-left">
              <el-input
                v-model="proxySearchQuery"
                placeholder="搜索节点名称、类型、服务器或端口..."
                size="small"
                style="width: 320px;"
                clearable
              >
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
              <span class="tb-count-text">共 {{ filteredEditorProxies.length }} / {{ editorProxies.length }} 个节点</span>
            </div>
            <div class="editor-toolbar-right">
              <button class="xui-std-btn btn-sm" :disabled="testingProfileDelays" @click="handleTestAllProfileNodesDelay">
                <el-icon v-if="!testingProfileDelays"><Odometer /></el-icon>
                <el-icon v-else class="is-loading"><Loading /></el-icon>
                <span>{{ testingProfileDelays ? '真延迟测定中...' : '真延迟测试 (Unified)' }}</span>
              </button>
              <button class="xui-primary-btn btn-sm" @click="openAddNodeModal">
                <el-icon><Plus /></el-icon>
                <span>添加节点</span>
              </button>
              <el-popconfirm
                title="确定清空母本中所有节点吗？（不可撤销）"
                @confirm="handleClearAllProxies"
              >
                <template #reference>
                  <button class="xui-std-btn btn-sm danger-btn">清空所有节点</button>
                </template>
              </el-popconfirm>
            </div>
          </div>

          <!-- 节点卡片网格 -->
          <div class="proxies-cards-grid">
            <div
              v-for="(node, nIdx) in filteredEditorProxies"
              :key="node.name + '_' + nIdx"
              class="editor-node-card"
            >
              <div class="n-card-top">
                <span class="node-protocol-tag" :class="'proto-' + (node.type || 'unknown')">
                  {{ node.ports ? `${node.type} (跳跃)` : (node.type || 'custom') }}
                </span>
                <div class="n-card-actions">
                  <button class="n-icon-btn edit" title="编辑节点" @click="openEditNodeDetail(node)">
                    <el-icon><Edit /></el-icon>
                  </button>
                  <el-popconfirm
                    title="确定删除此节点？将同步从已加入的策略组中移除"
                    @confirm="handleDeleteProxy(node.name)"
                  >
                    <template #reference>
                      <button class="n-icon-btn delete" title="删除节点">
                        <el-icon><Delete /></el-icon>
                      </button>
                    </template>
                  </el-popconfirm>
                </div>
              </div>

              <el-tooltip :content="node.name" placement="top" :show-after="300" :enterable="false">
                <div class="n-card-title">
                  {{ node.name }}
                </div>
              </el-tooltip>

              <div class="n-card-server">
                <el-icon class="server-icon"><Connection /></el-icon>
                <span class="server-text" :title="(node.server || '-') + ':' + (node.ports || node.port || '-')">
                  {{ node.server || '-' }}:{{ node.ports || node.port || '-' }}
                </span>
              </div>

              <!-- 节点国家/区域 (在 IP/域名下一行显示) -->
              <div class="n-card-location">
                <el-icon class="loc-icon"><Location /></el-icon>
                <span
                  v-if="getNodeLocation(node, ipLocationMap).svg"
                  class="country-flag-svg"
                  v-html="getNodeLocation(node, ipLocationMap).svg"
                ></span>
                <span v-else class="loc-flag">{{ getNodeLocation(node, ipLocationMap).flag }}</span>
                <span class="loc-text" :title="getNodeLocation(node, ipLocationMap).fullText">
                  {{ getNodeLocation(node, ipLocationMap).text }}
                </span>
              </div>

              <div class="n-card-footer">
                <el-tooltip placement="top" :content="getNodeGroupsTooltip(node.name)">
                  <span class="groups-included-pill">
                    <el-icon style="margin-right: 4px;"><Files /></el-icon>
                    所属 {{ getNodeGroupsCount(node.name) }} 个策略组
                  </span>
                </el-tooltip>

                <span
                  class="node-delay-pill"
                  :class="node.delay === 0 ? 'delay-testing' : (node.delay !== undefined ? getDelayClass(node.delay) : 'delay-none')"
                  :title="node.delay > 0 ? `${node.delay} ms (Mihomo Unified Delay 真实延迟，点击重测)` : '点击单节点测真实延迟'"
                  @click.stop="handleTestSingleProfileNodeDelay(node)"
                >
                  <el-icon v-if="node.delay === 0" class="is-loading" style="margin-right: 2px;"><Loading /></el-icon>
                  {{ node.delay === 0 ? '测速中' : (node.delay > 0 ? `${node.delay} ms` : (node.delay === -1 ? '超时' : '测延迟')) }}
                </span>
              </div>
            </div>

            <div v-if="filteredEditorProxies.length === 0" class="editor-empty-tip">
              未找到匹配的代理节点
            </div>
          </div>
        </div>

        <!-- 3. YAML 源码面板 -->
        <div v-else class="editor-yaml-layout">
          <div class="yaml-toolbar-tip">
            <span>支持在线直接编辑 YAML 源码。在可视化界面与源码之间切换时，系统会自动双向同步与校验。</span>
          </div>
          <el-input
            v-model="rawYamlContent"
            type="textarea"
            :rows="24"
            class="code-textarea"
            style="font-family: Consolas, Monaco, monospace; font-size: 13px;"
            placeholder="正在加载 YAML 源码..."
          />
        </div>
      </div>

      <template #footer>
        <div class="editor-footer-flex">
          <div class="footer-callout">
            <span class="f-tip">修改后点击「保存更改」，系统将自动生成快照备份并更新母本文件。</span>
          </div>
          <div class="footer-btns">
            <button class="xui-std-btn" @click="profileEditorVisible = false">关闭</button>
            <button
              class="xui-primary-btn"
              style="margin-left: 10px;"
              :disabled="savingEditor"
              @click="handleSaveEditorData"
            >
              <el-icon v-if="savingEditor" class="is-loading"><Loading /></el-icon>
              <span>{{ savingEditor ? '保存中...' : '保存更改' }}</span>
            </button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 新建策略组弹窗 -->
    <el-dialog
      v-model="addGroupDialogVisible"
      title="新建策略组"
      width="540px"
      class="xui-custom-dialog"
    >
      <el-form label-position="top">
        <el-form-item label="策略组名称">
          <el-input v-model="newGroupForm.name" placeholder="例如: 港澳台节点" />
        </el-form-item>
        <el-form-item label="策略类型">
          <el-select v-model="newGroupForm.type" style="width: 100%;">
            <el-option label="select (手动选择)" value="select" />
            <el-option label="url-test (自动测速)" value="url-test" />
            <el-option label="fallback (故障转移)" value="fallback" />
            <el-option label="load-balance (负载均衡)" value="load-balance" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="newGroupForm.type !== 'select'" label="测速接口 URL">
          <el-input v-model="newGroupForm.url" placeholder="http://cp.cloudflare.com/generate_204" />
        </el-form-item>

        <!-- 关联域名规则 -->
        <div class="group-rules-section">
          <div class="rules-section-header">
            <span class="rules-section-title">分流域名规则 (选填)</span>
            <span class="rules-section-tip">新建策略组时同步添加域名规则（分流到此策略组）</span>
          </div>

          <div v-if="newGroupRules.length > 0" class="rules-list-container">
            <div v-for="(r, rIdx) in newGroupRules" :key="rIdx" class="rule-item-chip">
              <span class="rule-type-badge">{{ r.type }}</span>
              <span class="rule-payload-text" :title="r.payload">{{ r.payload }}</span>
              <button type="button" class="rule-del-btn" title="删除" @click.stop="removeNewGroupRule(rIdx)">×</button>
            </div>
          </div>
          <div v-else class="rules-empty-note">
            暂未添加域名规则（支持创建后随时在策略组中增删）
          </div>

          <div class="rule-add-bar">
            <el-select v-model="newGroupRuleType" size="small" style="width: 150px;">
              <el-option label="DOMAIN-SUFFIX" value="DOMAIN-SUFFIX" />
              <el-option label="DOMAIN" value="DOMAIN" />
              <el-option label="DOMAIN-KEYWORD" value="DOMAIN-KEYWORD" />
              <el-option label="GEOSITE" value="GEOSITE" />
            </el-select>
            <el-input
              v-model="newGroupRulePayload"
              size="small"
              placeholder="输入域名，如 openai.com"
              style="flex: 1;"
              @keyup.enter="addNewGroupRule"
            />
            <button type="button" class="xui-std-btn btn-xs" @click="addNewGroupRule">
              <el-icon><Plus /></el-icon>
              <span>添加规则</span>
            </button>
          </div>
        </div>
      </el-form>
      <template #footer>
        <button class="xui-std-btn" @click="addGroupDialogVisible = false">取消</button>
        <button class="xui-primary-btn" style="margin-left: 8px;" @click="confirmAddNewGroup">创建策略组</button>
      </template>
    </el-dialog>

    <!-- 添加 / 编辑节点弹窗 -->
    <el-dialog
      v-model="editNodeModalVisible"
      :title="isEditingExistingNode ? '编辑节点参数' : '添加节点至母本'"
      width="580px"
      class="xui-custom-dialog"
    >
      <div v-if="!isEditingExistingNode" class="node-import-mode-tabs" style="margin-bottom: 14px;">
        <div class="protocol-tabs-group">
          <button class="p-tab-btn" :class="{ active: nodeAddMode === 'link' }" @click="nodeAddMode = 'link'">粘贴分享链接导入</button>
          <button class="p-tab-btn" :class="{ active: nodeAddMode === 'form' }" @click="nodeAddMode = 'form'">手动表单填写</button>
        </div>
      </div>

      <div v-if="!isEditingExistingNode && nodeAddMode === 'link'">
        <el-form label-position="top">
          <el-form-item label="节点分享链接 (支持 vless / vmess / ss / hysteria2 / trojan 等)">
            <el-input
              v-model="nodeLinkInput"
              type="textarea"
              :rows="4"
              placeholder="例如: hysteria2://password@1.2.3.4:443?sni=example.com#香港节点"
            />
          </el-form-item>
        </el-form>
      </div>

      <div v-else>
        <el-form label-position="top">
          <div class="form-cols-2">
            <el-form-item label="节点名称">
              <el-input v-model="currentNodeForm.name" placeholder="请输入节点名称" />
            </el-form-item>
            <el-form-item label="协议类型">
              <el-select v-model="currentNodeForm.type" style="width: 100%;">
                <el-option label="hysteria2" value="hysteria2" />
                <el-option label="vless" value="vless" />
                <el-option label="vmess" value="vmess" />
                <el-option label="shadowsocks (ss)" value="ss" />
                <el-option label="trojan" value="trojan" />
              </el-select>
            </el-form-item>
          </div>
          <div class="form-cols-2">
            <el-form-item label="服务器地址 (IP / 域名)">
              <el-input v-model="currentNodeForm.server" placeholder="例如: 1.2.3.4" />
            </el-form-item>
            <el-form-item label="端口">
              <el-input v-model="currentNodeForm.port" placeholder="例如: 443 或 20000-40000 (端口跳跃)" />
            </el-form-item>
          </div>
          <el-form-item label="密码 / UUID / 密钥">
            <el-input v-model="currentNodeForm.password" placeholder="密码或 UUID" />
          </el-form-item>
          <div class="form-cols-2">
            <el-form-item label="SNI / ServerName (选填)">
              <el-input v-model="currentNodeForm.sni" placeholder="例如: example.com" />
            </el-form-item>
            <el-form-item label="跳过证书校验 (skip-cert-verify)">
              <el-switch v-model="currentNodeForm['skip-cert-verify']" />
            </el-form-item>
          </div>
        </el-form>
      </div>

      <template #footer>
        <button class="xui-std-btn" @click="editNodeModalVisible = false">取消</button>
        <button class="xui-primary-btn" style="margin-left: 8px;" @click="confirmSaveNode">
          {{ isEditingExistingNode ? '保存修改' : '确认添加' }}
        </button>
      </template>
    </el-dialog>

    <!-- 编辑策略组参数弹窗 -->
    <el-dialog
      v-model="editGroupModalVisible"
      :title="`编辑策略组: ${editingGroupForm.name}`"
      width="560px"
      class="xui-custom-dialog"
    >
      <el-form label-position="top">
        <el-form-item label="策略组名称">
          <el-input v-model="editingGroupForm.name" placeholder="策略组名称" />
        </el-form-item>
        <el-form-item label="策略类型 (Type)">
          <el-select v-model="editingGroupForm.type" style="width: 100%;">
            <el-option label="select (手动选择)" value="select" />
            <el-option label="url-test (自动测速)" value="url-test" />
            <el-option label="fallback (故障转移)" value="fallback" />
            <el-option label="load-balance (负载均衡)" value="load-balance" />
          </el-select>
        </el-form-item>
        <template v-if="editingGroupForm.type !== 'select'">
          <el-form-item label="测速接口 URL">
            <el-input v-model="editingGroupForm.url" placeholder="http://cp.cloudflare.com/generate_204" />
          </el-form-item>
          <div class="form-cols-2">
            <el-form-item label="测速间隔 (秒)">
              <el-input-number v-model="editingGroupForm.interval" :min="10" :max="86400" style="width: 100%;" />
            </el-form-item>
            <el-form-item label="容差 (ms)">
              <el-input-number v-model="editingGroupForm.tolerance" :min="0" :max="5000" style="width: 100%;" />
            </el-form-item>
          </div>
        </template>

        <!-- 编辑策略组：自动显示该策略组下的所有域名规则，可以增删 -->
        <div class="group-rules-section">
          <div class="rules-section-header">
            <span class="rules-section-title">该策略组下的域名规则 (共 {{ currentGroupRules.length }} 条)</span>
            <span class="rules-section-tip">所有命中此类域名的流量都将被路由到此策略组</span>
          </div>

          <!-- 规则列表 -->
          <div class="rules-list-container">
            <div v-for="r in currentGroupRules" :key="r.index" class="rule-item-chip">
              <span class="rule-type-badge">{{ r.type }}</span>
              <span class="rule-payload-text" :title="r.payload">{{ r.payload }}</span>
              <button type="button" class="rule-del-btn" title="删除此规则" @click.stop="deleteGroupRule(r.index)">×</button>
            </div>
            <div v-if="currentGroupRules.length === 0" class="rules-empty-note">
              此策略组暂无专属分流域名规则
            </div>
          </div>

          <!-- 增补新规则 -->
          <div class="rule-add-bar">
            <el-select v-model="editGroupRuleType" size="small" style="width: 150px;">
              <el-option label="DOMAIN-SUFFIX" value="DOMAIN-SUFFIX" />
              <el-option label="DOMAIN" value="DOMAIN" />
              <el-option label="DOMAIN-KEYWORD" value="DOMAIN-KEYWORD" />
              <el-option label="GEOSITE" value="GEOSITE" />
            </el-select>
            <el-input
              v-model="editGroupRulePayload"
              size="small"
              placeholder="输入域名，如 google.com 或 openai"
              style="flex: 1;"
              @keyup.enter="addRuleToCurrentGroup"
            />
            <button type="button" class="xui-std-btn btn-xs" @click="addRuleToCurrentGroup">
              <el-icon><Plus /></el-icon>
              <span>添加规则</span>
            </button>
          </div>
        </div>
      </el-form>
      <template #footer>
        <button class="xui-std-btn" @click="editGroupModalVisible = false">取消</button>
        <button class="xui-primary-btn" style="margin-left: 8px;" @click="confirmSaveGroupEdit">保存设置</button>
      </template>
    </el-dialog>

    <!-- 向策略组添加节点弹窗 -->
    <el-dialog
      v-model="addNodesModalVisible"
      :title="`向「${targetGroupForAdding?.name || ''}」添加节点`"
      width="700px"
      class="xui-custom-dialog"
    >
      <div class="add-nodes-modal-body">
        <div class="add-nodes-toolbar">
          <el-input
            v-model="addNodesSearchQuery"
            placeholder="搜索待添加节点名称或协议..."
            size="small"
            style="width: 260px;"
            clearable
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <div class="quick-pick-btns">
            <button class="xui-std-btn btn-xs" @click="selectAllProxiesToAdd">全选母本节点</button>
            <button class="xui-std-btn btn-xs" @click="selectDirectRejectToAdd">+ 直连/拦截</button>
            <button class="xui-std-btn btn-xs" @click="selectedNodesToAdd = []">清空勾选</button>
          </div>
        </div>

        <div class="add-nodes-scroll-area">
          <!-- 1. 内置出站 -->
          <div class="node-category-section">
            <div class="cat-title">内置出站</div>
            <div class="cat-checkbox-grid">
              <label
                v-for="item in ['DIRECT', 'REJECT']"
                :key="item"
                class="node-select-item"
                :class="{
                  'already-in': isItemInTargetGroup(item),
                  'selected': selectedNodesToAdd.includes(item)
                }"
              >
                <input
                  type="checkbox"
                  :value="item"
                  :disabled="isItemInTargetGroup(item)"
                  v-model="selectedNodesToAdd"
                />
                <span class="z-proto-tag" :class="'proto-' + item.toLowerCase()">{{ item }}</span>
                <span class="select-item-name">{{ item }}</span>
                <span v-if="isItemInTargetGroup(item)" class="already-badge">已在组内</span>
              </label>
            </div>
          </div>

          <!-- 2. 其它策略组 -->
          <div v-if="candidateGroupsList.length > 0" class="node-category-section">
            <div class="cat-title">其它策略组 (嵌套引用)</div>
            <div class="cat-checkbox-grid">
              <label
                v-for="grp in candidateGroupsList"
                :key="grp.name"
                class="node-select-item"
                :class="{
                  'already-in': isItemInTargetGroup(grp.name),
                  'selected': selectedNodesToAdd.includes(grp.name)
                }"
              >
                <input
                  type="checkbox"
                  :value="grp.name"
                  :disabled="isItemInTargetGroup(grp.name)"
                  v-model="selectedNodesToAdd"
                />
                <span class="z-proto-tag proto-group">GROUP</span>
                <span class="select-item-name" :title="grp.name">{{ grp.name }}</span>
                <span v-if="isItemInTargetGroup(grp.name)" class="already-badge">已在组内</span>
              </label>
            </div>
          </div>

          <!-- 3. 母本节点 -->
          <div class="node-category-section">
            <div class="cat-title">母本节点 ({{ filteredCandidatesProxies.length }})</div>
            <div class="cat-checkbox-grid">
              <label
                v-for="p in filteredCandidatesProxies"
                :key="p.name"
                class="node-select-item"
                :class="{
                  'already-in': isItemInTargetGroup(p.name),
                  'selected': selectedNodesToAdd.includes(p.name)
                }"
              >
                <input
                  type="checkbox"
                  :value="p.name"
                  :disabled="isItemInTargetGroup(p.name)"
                  v-model="selectedNodesToAdd"
                />
                <span class="z-proto-tag" :class="'proto-' + (p.type || 'custom')">{{ p.type || 'custom' }}</span>
                <span class="select-item-name" :title="p.name">{{ p.name }}</span>
                <span v-if="isItemInTargetGroup(p.name)" class="already-badge">已在组内</span>
              </label>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <button class="xui-std-btn" @click="addNodesModalVisible = false">取消</button>
        <button
          class="xui-primary-btn"
          style="margin-left: 8px;"
          :disabled="selectedNodesToAdd.length === 0"
          @click="confirmAddNodesToGroup"
        >
          确认添加 ({{ selectedNodesToAdd.length }})
        </button>
      </template>
    </el-dialog>

    <!-- 备份列表抽屉 -->
    <el-drawer
      v-model="backupDrawerVisible"
      :title="`[${backupProfileName}] 快照备份记录 (${backupsList.length}/20)`"
      size="440px"
      class="xui-custom-drawer"
    >
      <div style="font-size: 12px; color: #8b949e; margin-bottom: 14px; padding: 0 10px; line-height: 1.5;">系统已开启自动配额保护：每个母本最多保留最新的 20 份快照，超出时将自动轮换清理最旧版本。</div>
      <el-timeline v-if="backupsList.length > 0" style="padding-left: 10px;">
        <el-timeline-item
          v-for="b in backupsList"
          :key="b.filename"
          :timestamp="b.created_at"
          placement="top"
        >
          <div class="backup-box-row">
            <div class="b-details">
              <span class="b-title">{{ b.filename }}</span>
              <span class="b-filesize">{{ (b.size / 1024).toFixed(1) }} KB</span>
            </div>
            <div style="margin-top: 8px; text-align: right; display: flex; justify-content: flex-end; gap: 8px;">
              <el-popconfirm title="确认回退至该快照？" @confirm="handleRestoreBackup(b.filename)">
                <template #reference>
                  <el-button size="small" type="warning" plain>恢复此版本</el-button>
                </template>
              </el-popconfirm>
              <el-popconfirm title="确认永久删除此快照备份？" @confirm="handleDeleteBackup(b.filename)">
                <template #reference>
                  <el-button size="small" type="danger" plain>删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>
      <div v-else class="muted-text" style="text-align: center; padding: 40px 0;">暂无快照备份</div>
    </el-drawer>
    <!-- 提取外部节点进度弹窗 (完全 3X-UI 暗黑风格) -->
    <el-dialog
      v-model="fetchProgressVisible"
      title="提取外部节点进度"
      width="560px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="fetchProgressData.isDone || fetchProgressData.isError"
      class="xui-custom-dialog fetch-progress-dialog"
    >
      <div class="fetch-progress-body">
        <!-- 顶部主状态展示 -->
        <div class="progress-main-status">
          <div class="status-icon-wrap">
            <el-icon v-if="fetchProgressData.isDone" :size="30" style="color: #4ade80;"><CircleCheck /></el-icon>
            <el-icon v-else-if="fetchProgressData.isError" :size="30" style="color: #f87171;"><CircleClose /></el-icon>
            <el-icon v-else class="is-loading" :size="30" style="color: #38bdf8;"><Loading /></el-icon>
          </div>
          <div class="status-texts">
            <div class="status-primary-title">
              {{ fetchProgressData.isDone ? '节点提取与延迟过滤完成' : (fetchProgressData.isError ? '提取失败' : '正在提取外部节点...') }}
            </div>
            <div class="status-sub-msg">
              {{ fetchProgressData.msg || '正在准备连接...' }}
            </div>
          </div>
        </div>

        <!-- 3X-UI 高质感进度条 -->
        <div class="progress-bar-container">
          <div class="progress-track">
            <div
              class="progress-fill"
              :class="{
                'fill-success': fetchProgressData.isDone,
                'fill-error': fetchProgressData.isError,
                'fill-active': !fetchProgressData.isDone && !fetchProgressData.isError
              }"
              :style="{ width: fetchProgressData.percent + '%' }"
            ></div>
          </div>
          <div class="progress-percent-label">{{ fetchProgressData.percent }}%</div>
        </div>

        <!-- 实时数据统计卡片 -->
        <div class="progress-stats-grid">
          <div class="stat-mini-card">
            <span class="stat-num">{{ fetchProgressData.total_raw || 0 }}</span>
            <span class="stat-lbl">原始节点</span>
          </div>
          <div class="stat-mini-card">
            <span class="stat-num text-green">{{ fetchProgressData.alive_count || 0 }}</span>
            <span class="stat-lbl">有效存活</span>
          </div>
          <div class="stat-mini-card">
            <span class="stat-num text-red">{{ fetchProgressData.filtered_count || 0 }}</span>
            <span class="stat-lbl">过滤失效/广告</span>
          </div>
        </div>

        <!-- 流程步骤状态线 -->
        <div class="progress-steps-list">
          <div class="p-step-item" :class="getStepClass(1)">
            <span class="step-indicator">
              <el-icon v-if="fetchProgressData.step > 1" :size="12"><Check /></el-icon>
              <span v-else>1</span>
            </span>
            <span class="step-text">连接订阅源并拉取配置数据</span>
          </div>

          <div class="p-step-item" :class="getStepClass(2)">
            <span class="step-indicator">
              <el-icon v-if="fetchProgressData.step > 2" :size="12"><Check /></el-icon>
              <span v-else>2</span>
            </span>
            <span class="step-text">解析 Vless / Vmess / SS / Hysteria 协议节点</span>
          </div>

          <div class="p-step-item" :class="getStepClass(3)">
            <span class="step-indicator">
              <el-icon v-if="fetchProgressData.step > 3" :size="12"><Check /></el-icon>
              <span v-else>3</span>
            </span>
            <span class="step-text">Mihomo 内核开启 Unified Delay 并发测定真实延迟并过滤死节点</span>
          </div>

          <div class="p-step-item" :class="getStepClass(4)">
            <span class="step-indicator">
              <el-icon v-if="fetchProgressData.step >= 4" :size="12"><Check /></el-icon>
              <span v-else>4</span>
            </span>
            <span class="step-text">卡片池就绪，完成 URL Test 延迟测定</span>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer-actions">
          <button
            v-if="!fetchProgressData.isDone && !fetchProgressData.isError"
            class="xui-std-btn"
            @click="cancelFetchProgress"
          >
            取消提取
          </button>
          <button
            v-if="fetchProgressData.isError"
            class="xui-std-btn"
            @click="fetchProgressVisible = false"
          >
            关闭
          </button>
          <button
            v-if="fetchProgressData.isDone"
            class="xui-primary-btn"
            @click="finishFetchAndCloseDialog"
          >
            进入卡片池 ({{ fetchProgressData.alive_count || 0 }})
          </button>
        </div>
      </template>
    </el-dialog>
    <!-- 上传母本到远程指定目标弹窗 (支持 SMB / FTP / WebDAV / 本地UNC，默认覆盖替换) -->
    <el-dialog
      v-model="remoteModalVisible"
      title="上传母本至指定目标 (SMB / FTP / WebDAV)"
      width="640px"
      class="xui-custom-dialog remote-upload-dialog"
    >
      <div class="remote-dialog-body">
        <!-- 目标母本与预设选择 -->
        <div class="remote-top-bar">
          <div class="remote-target-select-row">
            <span class="r-label">要上传的母本:</span>
            <el-select v-model="targetProfileForUpload" size="small" style="width: 210px;">
              <el-option
                v-for="p in profileList"
                :key="p.name"
                :label="p.name"
                :value="p.name"
              />
            </el-select>
          </div>

          <div class="remote-preset-select-row" v-if="savedRemoteTargets.length > 0">
            <span class="r-label">常用目标:</span>
            <el-select
              v-model="selectedRemoteTargetId"
              placeholder="载入常用目标"
              size="small"
              style="width: 170px;"
              @change="applyRemoteTargetPreset"
              clearable
            >
              <el-option
                v-for="t in savedRemoteTargets"
                :key="t.id"
                :label="t.name"
                :value="t.id"
              />
            </el-select>
            <el-popconfirm
              v-if="selectedRemoteTargetId"
              title="确定删除此常用目标？"
              @confirm="handleDeleteRemoteTarget(selectedRemoteTargetId)"
            >
              <template #reference>
                <el-button size="small" type="danger" link>删除目标</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>

        <!-- 协议切换栏 (3X-UI 风格胶囊组) -->
        <div class="protocol-tabs-wrap">
          <div class="protocol-tabs-group">
            <button
              class="p-tab-btn"
              :class="{ active: remoteForm.protocol === 'webdav' }"
              @click="switchRemoteProtocol('webdav')"
            >
              WebDAV
            </button>
            <button
              class="p-tab-btn"
              :class="{ active: remoteForm.protocol === 'smb' }"
              @click="switchRemoteProtocol('smb')"
            >
              SMB (Samba)
            </button>
            <button
              class="p-tab-btn"
              :class="{ active: remoteForm.protocol === 'ftp' }"
              @click="switchRemoteProtocol('ftp')"
            >
              FTP
            </button>
            <button
              class="p-tab-btn"
              :class="{ active: remoteForm.protocol === 'local' }"
              @click="switchRemoteProtocol('local')"
            >
              本地/共享路径
            </button>
          </div>
        </div>

        <!-- 表单区域 -->
        <el-form label-position="top" class="remote-upload-form">
          <!-- WebDAV -->
          <template v-if="remoteForm.protocol === 'webdav'">
            <el-form-item label="WebDAV 完整 URL (填文件夹路径或具体文件名均可)">
              <el-input
                v-model="remoteForm.url"
                placeholder="例如: http://192.168.1.1:5005/dav 或 http://.../dav/clash.yaml"
              />
            </el-form-item>
            <div class="form-cols-2">
              <el-form-item label="用户名 (选填)">
                <el-input v-model="remoteForm.username" placeholder="留空为无认证" />
              </el-form-item>
              <el-form-item label="密码 (选填)">
                <el-input v-model="remoteForm.password" type="password" show-password placeholder="密码" />
              </el-form-item>
            </div>
            <div class="form-tip-line">
              只需填至目标文件夹即可（系统自动以母本名称保存），也支持具体指定文件名。适用于 Alist、群晖、Nextcloud 等。
            </div>
          </template>

          <!-- SMB (Samba) -->
          <template v-else-if="remoteForm.protocol === 'smb'">
            <el-form-item label="服务器 IP / 主机名 (支持直接输入完整 UNC 路径如 \192.168.1.1\share\clash.yaml)">
              <el-input v-model="remoteForm.server" placeholder="例如: 192.168.1.1" />
            </el-form-item>
            <div class="form-cols-2">
              <el-form-item label="共享文件夹 (Share Name)">
                <el-input v-model="remoteForm.share" placeholder="例如: share 或 data" />
              </el-form-item>
              <el-form-item label="远程路径 / 目标文件名 (选填，仅填子文件夹即可)">
                <el-input v-model="remoteForm.path" placeholder="例如: openclash 或 openclash/config.yaml (留空默认根目录)" />
              </el-form-item>
            </div>
            <div class="form-cols-3">
              <el-form-item label="用户名 (选填)">
                <el-input v-model="remoteForm.username" placeholder="匿名请留空" />
              </el-form-item>
              <el-form-item label="密码 (选填)">
                <el-input v-model="remoteForm.password" type="password" show-password placeholder="密码" />
              </el-form-item>
              <el-form-item label="端口">
                <el-input v-model="remoteForm.port" placeholder="445" />
              </el-form-item>
            </div>
            <div class="form-tip-line">
              只需填子目录即可（自动以母本文件名保存），也支持具体指定文件名。适用于 Windows 共享、NAS、软路由 SMB。
            </div>
          </template>

          <!-- FTP -->
          <template v-else-if="remoteForm.protocol === 'ftp'">
            <div class="form-cols-2-1">
              <el-form-item label="FTP 主机地址 (IP 或域名)">
                <el-input v-model="remoteForm.host" placeholder="例如: 192.168.1.1" />
              </el-form-item>
              <el-form-item label="端口">
                <el-input v-model="remoteForm.port" placeholder="21" />
              </el-form-item>
            </div>
            <el-form-item label="远程保存绝对路径 (填文件夹或具体文件名均可)">
              <el-input v-model="remoteForm.path" placeholder="例如: /etc/openclash/config 或 .../config.yaml" />
            </el-form-item>
            <div class="form-cols-2">
              <el-form-item label="用户名">
                <el-input v-model="remoteForm.username" placeholder="例如: root 或 anonymous" />
              </el-form-item>
              <el-form-item label="密码">
                <el-input v-model="remoteForm.password" type="password" show-password placeholder="密码" />
              </el-form-item>
            </div>
            <div class="form-tip-line">
              填至目标文件夹即可（自动以母本文件名保存，并自动递归创建父目录），也支持具体指定文件名。
            </div>
          </template>

          <!-- 本地 / UNC 路径 -->
          <template v-else>
            <el-form-item label="目标本地路径 / 局域网 UNC 共享路径 (填文件夹或具体文件名均可)">
              <el-input
                v-model="remoteForm.path"
                placeholder="例如: D:\OpenClash 或 \\192.168.1.1\share\config.yaml"
              />
            </el-form-item>
            <div class="form-tip-line">
              填文件夹即可（自动以母本文件名保存），支持本地磁盘、已映射网络驱动器或局域网 UNC 共享。
            </div>
          </template>

          <!-- 选项栏 -->
          <div class="remote-options-box">
            <div class="opt-row">
              <el-checkbox v-model="remoteForm.overwrite" :disabled="true">
                <span class="opt-txt">默认覆盖替换目标文件 (已启用)</span>
              </el-checkbox>
            </div>
            <div class="opt-row save-target-row">
              <el-checkbox v-model="saveAsTargetOption">
                <span class="opt-txt">同时保存为常用目标 (便于下次一键上传)</span>
              </el-checkbox>
              <el-input
                v-if="saveAsTargetOption"
                v-model="saveTargetName"
                placeholder="为常用目标命名 (如: OpenWrt主路由)"
                size="small"
                style="width: 220px; margin-left: 12px;"
              />
            </div>
          </div>
        </el-form>
      </div>

      <template #footer>
        <div class="remote-footer-flex">
          <button
            class="xui-std-btn"
            :disabled="testingRemote || uploadingRemote"
            @click="handleTestRemoteConnection"
          >
            <el-icon v-if="testingRemote" class="is-loading"><Loading /></el-icon>
            <span>{{ testingRemote ? '测试中...' : '测试连接' }}</span>
          </button>

          <div style="display: flex; gap: 8px;">
            <button class="xui-std-btn" @click="remoteModalVisible = false">取消</button>
            <button
              class="xui-primary-btn"
              :disabled="uploadingRemote"
              @click="handleUploadToRemote"
            >
              <el-icon v-if="uploadingRemote" class="is-loading"><Loading /></el-icon>
              <el-icon v-else><Upload /></el-icon>
              <span>{{ uploadingRemote ? '上传传输中...' : '确认上传并覆盖替换' }}</span>
            </button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 修改网页访问密码弹窗 (Docker 模式) -->
    <el-dialog
      v-model="changePasswordDialogVisible"
      title="修改访问密码"
      width="440px"
      class="xui-custom-dialog"
    >
      <el-form label-position="top">
        <el-form-item label="当前原访问密码">
          <el-input v-model="changePasswordForm.old_password" type="password" show-password placeholder="请输入当前密码" />
        </el-form-item>
        <el-form-item label="新访问密码">
          <el-input v-model="changePasswordForm.new_password" type="password" show-password placeholder="请输入新密码 (至少4位)" />
        </el-form-item>
        <el-form-item label="确认新访问密码">
          <el-input v-model="changePasswordForm.confirm_password" type="password" show-password placeholder="请再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <button class="xui-std-btn" @click="changePasswordDialogVisible = false">取消</button>
        <button
          class="xui-primary-btn"
          style="margin-left: 8px;"
          :disabled="submittingChangePassword"
          @click="handleConfirmChangePassword"
        >
          {{ submittingChangePassword ? '正在修改...' : '确认修改' }}
        </button>
      </template>
    </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Folder, Collection, Download, Search,
  Upload, Check, Plus, UploadFilled,
  DocumentCopy, Connection, Files, CircleCheck, CircleClose, Loading, Link,
  Close, Delete, Edit, Lock, Key, SwitchButton, Odometer, Location
} from '@element-plus/icons-vue'
import * as api from './api'
import { getNodeLocation } from './utils/location'

// 访问认证与安全模式状态 (针对 Docker 容器网页密码保护)
const authStatus = ref({
  loading: true,
  auth_required: false,
  is_docker: false,
  is_initialized: true,
  logged_in: true
})
const initPasswordForm = ref({ password: '', confirm_password: '' })
const loginPassword = ref('')
const authErrorMessage = ref('')
const submittingAuth = ref(false)

// 修改密码弹窗状态
const changePasswordDialogVisible = ref(false)
const changePasswordForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const submittingChangePassword = ref(false)

const checkAuthStatus = async () => {
  authStatus.value.loading = true
  authErrorMessage.value = ''
  try {
    const res = await api.getAuthStatus()
    authStatus.value = {
      loading: false,
      auth_required: Boolean(res.data.auth_required),
      is_docker: Boolean(res.data.is_docker),
      is_initialized: Boolean(res.data.is_initialized),
      logged_in: Boolean(res.data.logged_in)
    }
  } catch (err) {
    console.error('获取认证状态失败:', err)
    authStatus.value.loading = false
  }
}

// 供 axios 响应拦截器 401 触发的全局失效通知
window.__handleAuthExpired = () => {
  if (authStatus.value.auth_required) {
    authStatus.value.logged_in = false
    ElMessage.warning('登录凭证已失效，请重新输入密码')
  }
}

const handleInitPassword = async () => {
  const p1 = initPasswordForm.value.password.trim()
  const p2 = initPasswordForm.value.confirm_password.trim()
  authErrorMessage.value = ''
  if (!p1) {
    authErrorMessage.value = '请输入访问密码'
    return
  }
  if (p1.length < 4) {
    authErrorMessage.value = '为保障安全，密码长度不能少于 4 位字符'
    return
  }
  if (p1 !== p2) {
    authErrorMessage.value = '两次输入的密码不一致，请重新确认'
    return
  }

  submittingAuth.value = true
  try {
    const res = await api.initAuth(p1, p2)
    if (res.data.token) {
      localStorage.setItem('ymlmanage_token', res.data.token)
    }
    authStatus.value.is_initialized = true
    authStatus.value.logged_in = true
    ElMessage.success('系统访问密码设置成功，已为您自动登录！')
    await initAppContent()
  } catch (err) {
    authErrorMessage.value = err.response?.data?.detail || err.message || '初始化失败，请重试'
  } finally {
    submittingAuth.value = false
  }
}

const handleLogin = async () => {
  const pwd = loginPassword.value.trim()
  authErrorMessage.value = ''
  if (!pwd) {
    authErrorMessage.value = '请输入访问密码'
    return
  }

  submittingAuth.value = true
  try {
    const res = await api.loginAuth(pwd)
    if (res.data.token) {
      localStorage.setItem('ymlmanage_token', res.data.token)
    }
    authStatus.value.logged_in = true
    ElMessage.success('验证成功，已进入控制台')
    await initAppContent()
  } catch (err) {
    authErrorMessage.value = err.response?.data?.detail || '访问密码错误，请重新输入'
  } finally {
    submittingAuth.value = false
  }
}

const handleLogout = async () => {
  try {
    await api.logoutAuth()
  } catch (e) {}
  localStorage.removeItem('ymlmanage_token')
  authStatus.value.logged_in = false
  loginPassword.value = ''
  authErrorMessage.value = ''
  ElMessage.info('已安全退出登录')
}

const openChangePasswordDialog = () => {
  changePasswordForm.value = { old_password: '', new_password: '', confirm_password: '' }
  changePasswordDialogVisible.value = true
}

const handleConfirmChangePassword = async () => {
  const f = changePasswordForm.value
  if (!f.old_password) {
    ElMessage.warning('请输入当前旧密码')
    return
  }
  if (!f.new_password || f.new_password.length < 4) {
    ElMessage.warning('新密码长度不能少于 4 位字符')
    return
  }
  if (f.new_password !== f.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  submittingChangePassword.value = true
  try {
    const res = await api.changePassword(f)
    if (res.data.token) {
      localStorage.setItem('ymlmanage_token', res.data.token)
    }
    changePasswordDialogVisible.value = false
    ElMessage.success('访问密码已成功修改并已更新登录凭证！')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || err.message || '修改密码失败')
  } finally {
    submittingChangePassword.value = false
  }
}

const profileList = ref([])
const currentProfile = ref('')
const currentGroups = ref([])
const currentProxyCount = ref(0)

const savedSources = ref([])
const selectedSourceId = ref('')
const testUrlsList = ref([])
const activeTestUrl = ref('http://cp.cloudflare.com/generate_204')
const filterDeadOption = ref(true)

const isDomesticTestUrl = computed(() => {
  const u = activeTestUrl.value || ''
  return u.includes('miui') || u.includes('hicloud') || u.includes('vivo') || u.includes('qualcomm')
})

const fetchUrl = ref('')
const fetching = ref(false)
const hasFetched = ref(false)
const fetchedNodes = ref([])
const totalRawCount = ref(0)
const filteredCount = ref(0)
const newCount = ref(0)
const existingCount = ref(0)
const ipLocationMap = ref({})

const resolveMissingLocations = async (nodes = []) => {
  if (!nodes || nodes.length === 0) return
  const unknownServers = new Set()
  for (const n of nodes) {
    if (!n) continue
    const loc = getNodeLocation(n, ipLocationMap.value)
    if (loc.code === 'UN' && n.server) {
      unknownServers.add(String(n.server).trim())
    }
  }
  const toQuery = Array.from(unknownServers).filter(s => s && !ipLocationMap.value[s])
  if (toQuery.length === 0) return

  try {
    const res = await api.lookupIpLocations(toQuery)
    if (res && res.data && res.data.data) {
      ipLocationMap.value = {
        ...ipLocationMap.value,
        ...res.data.data
      }
    }
  } catch (err) {
    // 忽略异步网络归属地查询异常
  }
}

const searchKeyword = ref('')
const selectedNodeIds = ref([])



// 提取节点进度弹窗状态
const fetchProgressVisible = ref(false)
const fetchProgressData = ref({
  percent: 10,
  step: 1,
  msg: '正在连接订阅服务器拉取配置数据...',
  total_raw: 0,
  alive_count: 0,
  filtered_count: 0,
  isDone: false,
  isError: false
})
let fetchAbortController = null
let fetchAutoCloseTimer = null

const getStepClass = (stepNum) => {
  if (fetchProgressData.value.isError) {
    if (fetchProgressData.value.step === stepNum) return 'step-error'
    if (fetchProgressData.value.step > stepNum) return 'step-done'
    return 'step-pending'
  }
  if (fetchProgressData.value.step > stepNum || fetchProgressData.value.isDone) {
    return 'step-done'
  }
  if (fetchProgressData.value.step === stepNum) {
    return 'step-active'
  }
  return 'step-pending'
}

const cancelFetchProgress = () => {
  if (fetchAbortController) {
    fetchAbortController.abort()
  }
  fetchProgressVisible.value = false
  fetching.value = false
  ElMessage.info('已取消提取')
}

const finishFetchAndCloseDialog = () => {
  if (fetchAutoCloseTimer) {
    clearTimeout(fetchAutoCloseTimer)
    fetchAutoCloseTimer = null
  }
  fetchProgressVisible.value = false
  selectOnlyNew()
}

// 导入抽屉与持久化
const importDrawerVisible = ref(false)
const GROUPS_STORAGE_KEY_PREFIX = 'yml_manage_selected_groups_'
const OVERWRITE_STORAGE_KEY = 'yml_manage_inject_overwrite'

const getSavedOverwriteOption = () => {
  try {
    const saved = localStorage.getItem(OVERWRITE_STORAGE_KEY)
    if (saved !== null) return saved === 'true'
  } catch (e) {
    console.error('获取覆盖选项失败', e)
  }
  return true
}

const overwriteOption = ref(getSavedOverwriteOption())

watch(overwriteOption, (val) => {
  try {
    localStorage.setItem(OVERWRITE_STORAGE_KEY, String(val))
  } catch (e) {
    console.error('保存覆盖选项失败', e)
  }
})

const selectedGroupNames = ref([])
const importing = ref(false)

const saveCurrentGroupSelection = () => {
  if (!currentProfile.value || currentGroups.value.length === 0) return
  try {
    const storageKey = GROUPS_STORAGE_KEY_PREFIX + currentProfile.value
    localStorage.setItem(storageKey, JSON.stringify(selectedGroupNames.value))
  } catch (e) {
    console.error('保存策略组勾选状态失败', e)
  }
}

watch(selectedGroupNames, () => {
  saveCurrentGroupSelection()
}, { deep: true })

const loadSavedGroupSelection = () => {
  if (!currentProfile.value || currentGroups.value.length === 0) return
  const storageKey = GROUPS_STORAGE_KEY_PREFIX + currentProfile.value
  try {
    const saved = localStorage.getItem(storageKey)
    if (saved !== null) {
      const parsed = JSON.parse(saved)
      if (Array.isArray(parsed) && parsed.length > 0) {
        const validNames = new Set(currentGroups.value.map(g => g.name))
        const matched = parsed.filter(name => validNames.has(name))
        if (matched.length > 0) {
          selectedGroupNames.value = matched
          return
        }
      }
    }
  } catch (e) {
    console.error('解析策略组勾选状态失败', e)
  }
  // 若未保存过偏好或之前被重置，默认全选当前母本已有策略组
  selectedGroupNames.value = currentGroups.value.map(g => g.name)
  saveCurrentGroupSelection()
}

// 模态框
const profileModalVisible = ref(false)
const profileActiveTab = ref('list')
const newProfileName = ref('')
const newProfileUrl = ref('')
const downloadingProfile = ref(false)
const uploadedFile = ref(null)
const uploadingProfile = ref(false)
const templateProfileName = ref('母本模板副本')

const sourceModalVisible = ref(false)
const addSourceDialogVisible = ref(false)
const sourceForm = ref({ name: '', url: '', notes: '' })

// 远程同步与上传 (SMB / FTP / WebDAV)
const remoteModalVisible = ref(false)
const targetProfileForUpload = ref('')
const savedRemoteTargets = ref([])
const selectedRemoteTargetId = ref('')
const saveAsTargetOption = ref(false)
const saveTargetName = ref('')
const testingRemote = ref(false)
const uploadingRemote = ref(false)

const STORAGE_KEY = 'yml_manage_remote_form_state'

const defaultProtocolState = {
  webdav: { url: '', username: '', password: '' },
  smb: { server: '', share: '', path: '', port: '445', username: '', password: '' },
  ftp: { host: '', port: '21', path: '', username: '', password: '' },
  local: { path: '' }
}

const getStoredProtocolState = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch (e) {
    console.error('解析远程上传存储失败', e)
  }
  return {
    lastProtocol: 'webdav',
    selectedPresetId: '',
    ...defaultProtocolState
  }
}

const initialStoredState = getStoredProtocolState()
const initialProto = initialStoredState.lastProtocol || 'webdav'
const initialProtoData = initialStoredState[initialProto] || {}

const remoteForm = ref({
  protocol: initialProto,
  url: initialStoredState.webdav?.url || '',
  server: initialStoredState.smb?.server || '',
  share: initialStoredState.smb?.share || '',
  host: initialStoredState.ftp?.host || '',
  port: initialProto === 'ftp' ? (initialStoredState.ftp?.port || '21') : (initialStoredState.smb?.port || '445'),
  path: initialProtoData.path || '',
  username: initialProtoData.username || '',
  password: initialProtoData.password || '',
  overwrite: true
})

const saveFormToStorage = () => {
  try {
    const curr = getStoredProtocolState()
    curr.lastProtocol = remoteForm.value.protocol
    curr.selectedPresetId = selectedRemoteTargetId.value
    if (remoteForm.value.protocol === 'webdav') {
      curr.webdav = {
        url: remoteForm.value.url,
        username: remoteForm.value.username,
        password: remoteForm.value.password
      }
    } else if (remoteForm.value.protocol === 'smb') {
      curr.smb = {
        server: remoteForm.value.server,
        share: remoteForm.value.share,
        path: remoteForm.value.path,
        port: remoteForm.value.port || '445',
        username: remoteForm.value.username,
        password: remoteForm.value.password
      }
    } else if (remoteForm.value.protocol === 'ftp') {
      curr.ftp = {
        host: remoteForm.value.host,
        port: remoteForm.value.port || '21',
        path: remoteForm.value.path,
        username: remoteForm.value.username,
        password: remoteForm.value.password
      }
    } else if (remoteForm.value.protocol === 'local') {
      curr.local = {
        path: remoteForm.value.path
      }
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(curr))
  } catch (e) {
    console.error('保存远程上传表单到本地存储失败', e)
  }
}

watch(remoteForm, () => {
  saveFormToStorage()
}, { deep: true })

const openRemoteUploadDialog = (profileName) => {
  targetProfileForUpload.value = profileName || currentProfile.value
  remoteModalVisible.value = true
  loadRemoteTargets()
}

const switchRemoteProtocol = (proto) => {
  saveFormToStorage()
  remoteForm.value.protocol = proto
  const curr = getStoredProtocolState()
  const pData = curr[proto] || {}

  if (proto === 'webdav') {
    remoteForm.value.url = pData.url || ''
    remoteForm.value.username = pData.username || ''
    remoteForm.value.password = pData.password || ''
  } else if (proto === 'smb') {
    remoteForm.value.server = pData.server || ''
    remoteForm.value.share = pData.share || ''
    remoteForm.value.path = pData.path || ''
    remoteForm.value.port = pData.port || '445'
    remoteForm.value.username = pData.username || ''
    remoteForm.value.password = pData.password || ''
  } else if (proto === 'ftp') {
    remoteForm.value.host = pData.host || ''
    remoteForm.value.port = pData.port || '21'
    remoteForm.value.path = pData.path || ''
    remoteForm.value.username = pData.username || ''
    remoteForm.value.password = pData.password || ''
  } else if (proto === 'local') {
    remoteForm.value.path = pData.path || ''
  }

  saveFormToStorage()
}

const loadRemoteTargets = async () => {
  try {
    const res = await api.getRemoteTargets()
    savedRemoteTargets.value = res.data || []
    const curr = getStoredProtocolState()
    if (curr.selectedPresetId && savedRemoteTargets.value.some(t => t.id === curr.selectedPresetId)) {
      selectedRemoteTargetId.value = curr.selectedPresetId
    }
  } catch (err) {
    console.error('加载远程目标失败', err)
  }
}

const applyRemoteTargetPreset = (id) => {
  if (!id) {
    selectedRemoteTargetId.value = ''
    saveFormToStorage()
    return
  }
  const t = savedRemoteTargets.value.find(item => item.id === id)
  if (t) {
    const proto = t.protocol || 'webdav'
    remoteForm.value.protocol = proto
    remoteForm.value.url = t.url || ''
    remoteForm.value.server = t.server || t.host || ''
    remoteForm.value.host = t.host || t.server || ''
    remoteForm.value.port = t.port || (proto === 'ftp' ? '21' : proto === 'smb' ? '445' : '')
    remoteForm.value.share = t.share || ''
    remoteForm.value.path = t.path || ''
    remoteForm.value.username = t.username || ''
    remoteForm.value.password = t.password || ''
    remoteForm.value.overwrite = t.overwrite !== false
    saveFormToStorage()
  }
}

const handleDeleteRemoteTarget = async (id) => {
  try {
    await api.deleteRemoteTarget(id)
    ElMessage.success('已删除常用目标')
    selectedRemoteTargetId.value = ''
    await loadRemoteTargets()
  } catch (err) {
    ElMessage.error('删除目标失败: ' + (err.response?.data?.detail || err.message))
  }
}

const handleTestRemoteConnection = async () => {
  testingRemote.value = true
  try {
    const res = await api.testRemoteConnection({
      protocol: remoteForm.value.protocol,
      config: remoteForm.value
    })
    ElMessage.success(res.data.message || '连接测试成功！')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || err.message || '连接失败')
  } finally {
    testingRemote.value = false
  }
}

const handleUploadToRemote = async () => {
  if (!targetProfileForUpload.value) {
    ElMessage.warning('请选择要上传的母本')
    return
  }
  uploadingRemote.value = true
  try {
    const res = await api.uploadProfileToRemote({
      profile_name: targetProfileForUpload.value,
      protocol: remoteForm.value.protocol,
      config: remoteForm.value,
      overwrite: remoteForm.value.overwrite,
      save_target: saveAsTargetOption.value,
      target_name: saveTargetName.value
    })
    ElMessage.success({
      message: res.data.message || '上传成功，已默认覆盖替换！',
      duration: 5000
    })
    remoteModalVisible.value = false
    saveAsTargetOption.value = false
    saveTargetName.value = ''
    await loadRemoteTargets()
  } catch (err) {
    ElMessage.error('上传失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    uploadingRemote.value = false
  }
}

const handleDeleteBackup = async (filename) => {
  try {
    const res = await api.deleteBackup(backupProfileName.value, filename)
    ElMessage.success(res.data.message || '已成功删除快照')
    await openBackups(backupProfileName.value)
    await loadProfiles()
  } catch (err) {
    ElMessage.error('删除快照失败: ' + (err.response?.data?.detail || err.message))
  }
}

// 可视化编辑与源码编辑器
const profileEditorVisible = ref(false)
const editorProfileName = ref('')
const editorActiveTab = ref('groups') // groups | proxies | yaml
const loadingEditorData = ref(false)
const savingEditor = ref(false)

const editorProxies = ref([])
const editorGroups = ref([])
const editorRules = ref([])
const editorRulesCount = ref(0)
const rawYamlContent = ref('')
const testingProfileDelays = ref(false)

// 策略组子状态
const groupSearchQuery = ref('')
const selectedEditGroup = ref(null)
const nodesToAddToCurrentGroup = ref([])
const addGroupDialogVisible = ref(false)
const newGroupForm = ref({ name: '', type: 'select', url: 'http://cp.cloudflare.com/generate_204', interval: 300, tolerance: 50 })
const newGroupRules = ref([])
const newGroupRuleType = ref('DOMAIN-SUFFIX')
const newGroupRulePayload = ref('')

// 节点子状态
const proxySearchQuery = ref('')
const editNodeModalVisible = ref(false)
const isEditingExistingNode = ref(false)
const nodeAddMode = ref('link') // link | form
const nodeLinkInput = ref('')
const currentNodeForm = ref({
  name: '',
  type: 'hysteria2',
  server: '',
  port: 443,
  password: '',
  sni: '',
  'skip-cert-verify': true
})
let oldEditingNodeName = ''

const filteredEditorGroups = computed(() => {
  const q = groupSearchQuery.value.trim().toLowerCase()
  if (!q) return editorGroups.value
  return editorGroups.value.filter(g => (g.name || '').toLowerCase().includes(q) || (g.type || '').toLowerCase().includes(q))
})

const filteredEditorProxies = computed(() => {
  const q = proxySearchQuery.value.trim().toLowerCase()
  if (!q) return editorProxies.value
  return editorProxies.value.filter(p => {
    const loc = getNodeLocation(p, ipLocationMap.value)
    return (
      (p.name || '').toLowerCase().includes(q) ||
      (p.type || '').toLowerCase().includes(q) ||
      String(p.server || '').toLowerCase().includes(q) ||
      String(p.port || '').includes(q) ||
      (loc.text && loc.text.toLowerCase().includes(q)) ||
      (loc.flag && loc.flag.includes(q))
    )
  })
})

// 代理节点类型映射表（快速查询协议用于渲染标签）
const proxyTypeMap = computed(() => {
  const map = new Map()
  for (const p of editorProxies.value) {
    if (p && p.name) {
      map.set(p.name, p.type || 'proxy')
    }
  }
  return map
})

const getMemberType = (name) => {
  if (name === 'DIRECT') return 'direct'
  if (name === 'REJECT') return 'reject'
  if (editorGroups.value.some(g => g.name === name)) return 'group'
  return proxyTypeMap.value.get(name) || 'node'
}

// 策略组内节点拖拽排序状态
const dragGroupIndex = ref(null)
const dragNodeIndex = ref(null)
const dropTargetNodeIndex = ref(null)

// 策略组卡片与节点整卡拖拽排序（含滚轮滚动与边缘自动滚屏）
const groupsGridRef = ref(null)
const dragGroupCardIdx = ref(null)
const dropTargetGroupCardIdx = ref(null)

let autoScrollRaf = null
let autoScrollSpeed = 0
let autoScrollContainer = null
let lastDragClientX = 0
let lastDragClientY = 0

const performAutoScroll = () => {
  if (!autoScrollContainer || autoScrollSpeed === 0) {
    if (autoScrollRaf) {
      cancelAnimationFrame(autoScrollRaf)
      autoScrollRaf = null
    }
    return
  }
  autoScrollContainer.scrollTop += autoScrollSpeed

  // 当鼠标静止悬停在容器边缘、而滚动条在自动滚动时，实时计算当前悬停卡片更新放置目标
  if (dragGroupCardIdx.value !== null && lastDragClientX && lastDragClientY) {
    const elem = document.elementFromPoint(lastDragClientX, lastDragClientY)
    const cardElem = elem?.closest('.z-group-card')
    if (cardElem && cardElem.dataset && cardElem.dataset.groupIndex !== undefined) {
      dropTargetGroupCardIdx.value = parseInt(cardElem.dataset.groupIndex, 10)
    }
  }

  autoScrollRaf = requestAnimationFrame(performAutoScroll)
}

const checkEdgeAutoScroll = (e, container) => {
  if (!container) return
  const rect = container.getBoundingClientRect()
  const edgeZone = 90 // 触发自动滚动的边缘距离 (px)
  const mouseY = e.clientY

  if (mouseY >= rect.top - 40 && mouseY <= rect.top + edgeZone) {
    // 靠近顶部边缘：向上滚动
    const dist = Math.max(0, rect.top + edgeZone - mouseY)
    const ratio = Math.min(1, dist / edgeZone)
    autoScrollSpeed = -Math.round(ratio * 20 + 4)
    autoScrollContainer = container
    if (!autoScrollRaf) {
      autoScrollRaf = requestAnimationFrame(performAutoScroll)
    }
  } else if (mouseY >= rect.bottom - edgeZone && mouseY <= rect.bottom + 40) {
    // 靠近底部边缘：向下滚动
    const dist = Math.max(0, mouseY - (rect.bottom - edgeZone))
    const ratio = Math.min(1, dist / edgeZone)
    autoScrollSpeed = Math.round(ratio * 20 + 4)
    autoScrollContainer = container
    if (!autoScrollRaf) {
      autoScrollRaf = requestAnimationFrame(performAutoScroll)
    }
  } else {
    // 位于安全区域：停止边缘自动滚动
    autoScrollSpeed = 0
    if (autoScrollRaf) {
      cancelAnimationFrame(autoScrollRaf)
      autoScrollRaf = null
    }
  }
}

const stopAutoScroll = () => {
  autoScrollSpeed = 0
  autoScrollContainer = null
  if (autoScrollRaf) {
    cancelAnimationFrame(autoScrollRaf)
    autoScrollRaf = null
  }
}

const handleDragWheel = (e) => {
  if (dragGroupCardIdx.value === null && dragGroupIndex.value === null) return

  // 1. 拖拽策略组卡片时：鼠标滚轮直接滚动策略组网格容器
  if (dragGroupCardIdx.value !== null) {
    const grid = groupsGridRef.value || document.querySelector('.zashboard-groups-grid')
    if (grid) {
      grid.scrollTop += e.deltaY
      if (e.cancelable) e.preventDefault()
    }
    return
  }

  // 2. 拖拽节点 Chip 时：如果鼠标悬停在组内 chip 容器上且内容溢出则滚 chip 容器，否则滚动策略组网格
  if (dragGroupIndex.value !== null) {
    const elem = document.elementFromPoint(e.clientX, e.clientY)
    const chipsBox = elem?.closest('.z-card-chips-container')
    if (chipsBox && chipsBox.scrollHeight > chipsBox.clientHeight) {
      chipsBox.scrollTop += e.deltaY
      if (e.cancelable) e.preventDefault()
    } else {
      const grid = groupsGridRef.value || document.querySelector('.zashboard-groups-grid')
      if (grid) {
        grid.scrollTop += e.deltaY
        if (e.cancelable) e.preventDefault()
      }
    }
  }
}

const startDragScrollTracking = () => {
  window.addEventListener('wheel', handleDragWheel, { passive: false, capture: true })
  document.addEventListener('wheel', handleDragWheel, { passive: false, capture: true })
}

const stopDragScrollTracking = () => {
  stopAutoScroll()
  window.removeEventListener('wheel', handleDragWheel, { capture: true })
  document.removeEventListener('wheel', handleDragWheel, { capture: true })
}

const handleGroupCardDragStart = (e, gIdx) => {
  if (dragGroupIndex.value !== null) return
  dragGroupCardIdx.value = gIdx
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', 'card_' + gIdx)
  startDragScrollTracking()
}

const handleGroupCardDragOver = (e, gIdx) => {
  if (dragGroupIndex.value !== null) {
    if (groupsGridRef.value) {
      checkEdgeAutoScroll(e, groupsGridRef.value)
    }
    return
  }
  if (dragGroupCardIdx.value === null) return
  e.preventDefault()
  e.dataTransfer.dropEffect = 'move'
  dropTargetGroupCardIdx.value = gIdx
  lastDragClientX = e.clientX
  lastDragClientY = e.clientY
  if (groupsGridRef.value) {
    checkEdgeAutoScroll(e, groupsGridRef.value)
  }
}

const handleGroupsGridDragOver = (e) => {
  if (dragGroupCardIdx.value !== null || dragGroupIndex.value !== null) {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    lastDragClientX = e.clientX
    lastDragClientY = e.clientY
    if (groupsGridRef.value) {
      checkEdgeAutoScroll(e, groupsGridRef.value)
    }
  }
}

const handleGroupsGridDrop = (e) => {
  if (dragGroupIndex.value !== null) return
  e.preventDefault()
  if (dragGroupCardIdx.value !== null) {
    const fromGIdx = dragGroupCardIdx.value
    const fromGrp = filteredEditorGroups.value[fromGIdx]
    if (fromGrp) {
      const realFromIdx = editorGroups.value.findIndex(g => g.name === fromGrp.name)
      if (realFromIdx !== -1) {
        const moved = editorGroups.value.splice(realFromIdx, 1)[0]
        editorGroups.value.push(moved)
      }
    }
    handleGroupCardDragEnd()
  }
}

const handleGroupCardDragLeave = () => {
  // 保持 target
}

const handleGroupCardDrop = (e, targetGIdx) => {
  if (dragGroupIndex.value !== null) return
  e.preventDefault()
  const fromGIdx = dragGroupCardIdx.value
  if (fromGIdx === null || fromGIdx === targetGIdx) {
    handleGroupCardDragEnd()
    return
  }
  const fromGrp = filteredEditorGroups.value[fromGIdx]
  const targetGrp = filteredEditorGroups.value[targetGIdx]
  if (fromGrp && targetGrp) {
    const realFromIdx = editorGroups.value.findIndex(g => g.name === fromGrp.name)
    const realTargetIdx = editorGroups.value.findIndex(g => g.name === targetGrp.name)
    if (realFromIdx !== -1 && realTargetIdx !== -1 && realFromIdx !== realTargetIdx) {
      const moved = editorGroups.value.splice(realFromIdx, 1)[0]
      editorGroups.value.splice(realTargetIdx, 0, moved)
    }
  }
  handleGroupCardDragEnd()
}

const handleGroupCardDragEnd = () => {
  dragGroupCardIdx.value = null
  dropTargetGroupCardIdx.value = null
  stopDragScrollTracking()
}

const handleGroupNodeDragStart = (e, gIdx, pIdx) => {
  e.stopPropagation()
  dragGroupIndex.value = gIdx
  dragNodeIndex.value = pIdx
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', String(pIdx))
  startDragScrollTracking()
}

const handleGroupNodeDragOver = (e, gIdx, pIdx) => {
  if (dragGroupIndex.value !== gIdx) return
  e.dataTransfer.dropEffect = 'move'
  dropTargetNodeIndex.value = pIdx
  lastDragClientX = e.clientX
  lastDragClientY = e.clientY
  if (groupsGridRef.value) {
    checkEdgeAutoScroll(e, groupsGridRef.value)
  }
}

const handleGroupNodeDragLeave = () => {
  // 保持当前 target
}

const handleGroupNodeDrop = (e, gIdx, targetIdx) => {
  e.preventDefault()
  if (dragGroupIndex.value === null || dragGroupIndex.value !== gIdx) {
    handleGroupNodeDragEnd()
    return
  }
  const fromIdx = dragNodeIndex.value
  if (fromIdx === null || fromIdx === targetIdx) {
    handleGroupNodeDragEnd()
    return
  }
  const grp = filteredEditorGroups.value[gIdx]
  if (grp && grp.proxies) {
    const item = grp.proxies.splice(fromIdx, 1)[0]
    grp.proxies.splice(targetIdx, 0, item)
  }
  handleGroupNodeDragEnd()
}

const handleGroupContainerDrop = (e, grp, gIdx) => {
  e.preventDefault()
  if (dragGroupIndex.value === null || dragGroupIndex.value !== gIdx) {
    handleGroupNodeDragEnd()
    return
  }
  const fromIdx = dragNodeIndex.value
  if (fromIdx !== null && grp && grp.proxies && fromIdx < grp.proxies.length - 1) {
    const item = grp.proxies.splice(fromIdx, 1)[0]
    grp.proxies.push(item)
  }
  handleGroupNodeDragEnd()
}

const handleGroupNodeDragEnd = () => {
  dragGroupIndex.value = null
  dragNodeIndex.value = null
  dropTargetNodeIndex.value = null
  stopDragScrollTracking()
}

const removeNodeFromGroup = (grp, pIdx) => {
  if (!grp || !grp.proxies) return
  const removed = grp.proxies.splice(pIdx, 1)[0]
  ElMessage.info(`已将「${removed}」从策略组移除`)
}

// 编辑策略组属性弹窗状态
const editGroupModalVisible = ref(false)
const editingGroupTarget = ref(null)
const editingGroupForm = ref({ name: '', type: 'select', url: '', interval: 300, tolerance: 50 })
const editGroupRuleType = ref('DOMAIN-SUFFIX')
const editGroupRulePayload = ref('')

const currentGroupRules = computed(() => {
  if (!editingGroupTarget.value) return []
  const groupName = editingGroupTarget.value.name
  const list = []
  editorRules.value.forEach((r, idx) => {
    if (typeof r !== 'string') return
    const parts = r.split(',').map(s => s.trim())
    if (parts.length >= 3 && parts[2] === groupName) {
      list.push({
        index: idx,
        type: parts[0],
        payload: parts[1],
        policy: parts[2],
        raw: r
      })
    }
  })
  return list
})

const addRuleToCurrentGroup = () => {
  const payload = editGroupRulePayload.value.trim()
  if (!payload) {
    ElMessage.warning('请输入规则内容 (例如: google.com 或 openai)')
    return
  }
  if (!editingGroupTarget.value) return
  const currentGroupName = editingGroupTarget.value.name
  const type = editGroupRuleType.value

  // 1. 检查是否在当前策略组已存在
  const existsInCurrent = editorRules.value.some(r => {
    if (typeof r !== 'string') return false
    const parts = r.split(',').map(s => s.trim())
    return parts.length >= 3 &&
           parts[0].toUpperCase() === type.toUpperCase() &&
           parts[1].toLowerCase() === payload.toLowerCase() &&
           parts[2] === currentGroupName
  })
  if (existsInCurrent) {
    ElMessage.warning(`规则「${type},${payload}」已存在于当前策略组中`)
    return
  }

  // 2. 检查是否在其他策略组中存在
  const conflictRules = []
  editorRules.value.forEach((r, idx) => {
    if (typeof r !== 'string') return
    const parts = r.split(',').map(s => s.trim())
    if (parts.length >= 3 &&
        parts[0].toUpperCase() === type.toUpperCase() &&
        parts[1].toLowerCase() === payload.toLowerCase() &&
        parts[2] !== currentGroupName) {
      conflictRules.push({ index: idx, group: parts[2], raw: r })
    }
  })

  const doInsertCurrentRule = () => {
    const ruleStr = `${type},${payload},${currentGroupName}`
    const matchIdx = editorRules.value.findIndex(item => {
      const p = String(item).split(',')[0].trim().toUpperCase()
      return p === 'MATCH' || p === 'GEOIP'
    })
    if (matchIdx !== -1) {
      editorRules.value.splice(matchIdx, 0, ruleStr)
    } else {
      editorRules.value.push(ruleStr)
    }
    editGroupRulePayload.value = ''
    ElMessage.success(`已添加规则: ${ruleStr}`)
  }

  if (conflictRules.length > 0) {
    const otherGroups = [...new Set(conflictRules.map(c => c.group))].join('、')
    ElMessageBox.confirm(
      `规则「${type},${payload}」已存在于策略组「${otherGroups}」中，是否从原策略组删除并转入当前策略组「${currentGroupName}」？`,
      '规则冲突提示',
      {
        confirmButtonText: '删除原规则并转入',
        cancelButtonText: '取消',
        type: 'warning'
      }
    ).then(() => {
      // 从原策略组删除冲突规则
      editorRules.value = editorRules.value.filter(r => {
        if (typeof r !== 'string') return true
        const p = r.split(',').map(s => s.trim())
        return !(p.length >= 3 &&
                 p[0].toUpperCase() === type.toUpperCase() &&
                 p[1].toLowerCase() === payload.toLowerCase() &&
                 p[2] !== currentGroupName)
      })
      doInsertCurrentRule()
    }).catch(() => {
      ElMessage.info('已取消添加')
    })
  } else {
    doInsertCurrentRule()
  }
}

const deleteGroupRule = (ruleIndex) => {
  if (ruleIndex >= 0 && ruleIndex < editorRules.value.length) {
    const removed = editorRules.value.splice(ruleIndex, 1)[0]
    ElMessage.info(`已移除规则: ${removed}`)
  }
}

const openEditGroupModal = (grp) => {
  editingGroupTarget.value = grp
  editingGroupForm.value = {
    name: grp.name || '',
    type: grp.type || 'select',
    url: grp.url || 'http://cp.cloudflare.com/generate_204',
    interval: grp.interval || 300,
    tolerance: grp.tolerance || 50
  }
  editGroupRuleType.value = 'DOMAIN-SUFFIX'
  editGroupRulePayload.value = ''
  editGroupModalVisible.value = true
}

const confirmSaveGroupEdit = () => {
  const f = editingGroupForm.value
  const target = editingGroupTarget.value
  if (!target) return
  const oldName = target.name
  const newName = f.name.trim()
  if (!newName) {
    ElMessage.warning('策略组名称不能为空')
    return
  }
  if (oldName !== newName && editorGroups.value.some(g => g.name === newName)) {
    ElMessage.warning('策略组名称已存在')
    return
  }
  target.name = newName
  target.type = f.type
  if (f.type !== 'select') {
    target.url = f.url || 'http://cp.cloudflare.com/generate_204'
    target.interval = f.interval || 300
    target.tolerance = f.tolerance || 50
  } else {
    delete target.url
    delete target.interval
    delete target.tolerance
  }
  if (oldName !== newName) {
    editorGroups.value.forEach(g => {
      if (g.proxies) {
        g.proxies = g.proxies.map(p => (p === oldName ? newName : p))
      }
    })
    // 同步更新规则中的策略组名称
    if (editorRules.value && editorRules.value.length > 0) {
      editorRules.value = editorRules.value.map(ruleStr => {
        if (typeof ruleStr !== 'string') return ruleStr
        const parts = ruleStr.split(',').map(s => s.trim())
        if (parts.length >= 3 && parts[2] === oldName) {
          parts[2] = newName
          return parts.join(',')
        }
        return ruleStr
      })
    }
  }
  editGroupModalVisible.value = false
  ElMessage.success(`策略组「${newName}」已更新`)
}

// 向指定策略组添加节点弹窗状态
const addNodesModalVisible = ref(false)
const targetGroupForAdding = ref(null)
const addNodesSearchQuery = ref('')
const selectedNodesToAdd = ref([])

const openAddNodesToGroup = (grp) => {
  targetGroupForAdding.value = grp
  selectedNodesToAdd.value = []
  addNodesSearchQuery.value = ''
  addNodesModalVisible.value = true
}

const isItemInTargetGroup = (itemName) => {
  if (!targetGroupForAdding.value || !targetGroupForAdding.value.proxies) return false
  return targetGroupForAdding.value.proxies.includes(itemName)
}

const candidateGroupsList = computed(() => {
  if (!targetGroupForAdding.value) return []
  const currentName = targetGroupForAdding.value.name
  return editorGroups.value.filter(g => g.name !== currentName)
})

const filteredCandidatesProxies = computed(() => {
  const q = addNodesSearchQuery.value.trim().toLowerCase()
  if (!q) return editorProxies.value
  return editorProxies.value.filter(p =>
    (p.name || '').toLowerCase().includes(q) ||
    (p.type || '').toLowerCase().includes(q) ||
    String(p.server || '').toLowerCase().includes(q)
  )
})

const selectAllProxiesToAdd = () => {
  const currentSet = new Set(targetGroupForAdding.value?.proxies || [])
  const newSelected = new Set(selectedNodesToAdd.value)
  for (const p of filteredCandidatesProxies.value) {
    if (!currentSet.has(p.name)) {
      newSelected.add(p.name)
    }
  }
  selectedNodesToAdd.value = Array.from(newSelected)
}

const selectDirectRejectToAdd = () => {
  const currentSet = new Set(targetGroupForAdding.value?.proxies || [])
  const newSelected = new Set(selectedNodesToAdd.value)
  if (!currentSet.has('DIRECT')) newSelected.add('DIRECT')
  if (!currentSet.has('REJECT')) newSelected.add('REJECT')
  selectedNodesToAdd.value = Array.from(newSelected)
}

const confirmAddNodesToGroup = () => {
  const grp = targetGroupForAdding.value
  if (!grp) return
  if (!grp.proxies) grp.proxies = []
  const set = new Set(grp.proxies)
  let count = 0
  for (const item of selectedNodesToAdd.value) {
    if (!set.has(item)) {
      grp.proxies.push(item)
      set.add(item)
      count++
    }
  }
  addNodesModalVisible.value = false
  ElMessage.success(`成功向「${grp.name}」添加 ${count} 个节点`)
}


const backupDrawerVisible = ref(false)
const backupProfileName = ref('')
const backupsList = ref([])

const loadTestUrls = async () => {
  try {
    const res = await api.getTestUrls()
    testUrlsList.value = res.data.list || []
    if (!activeTestUrl.value && res.data.default_url) {
      activeTestUrl.value = res.data.default_url
    }
  } catch (err) {
    console.error('加载测速接口列表失败', err)
  }
}

const handleTestUrlChange = async (url) => {
  activeTestUrl.value = url
  if (currentProfile.value) {
    try {
      await api.updateProfileTestUrl(currentProfile.value, url)
      ElMessage.success('已切换测速接口为: ' + (testUrlsList.value.find(i => i.url === url)?.name || url))
    } catch (e) {
      console.error(e)
    }
  }
}

const systemInfo = ref({ lan_ip: '', port: 8080, lan_url: '', local_url: '' })

const loadSystemInfo = async () => {
  try {
    const res = await api.getSystemInfo()
    systemInfo.value = res.data
  } catch (err) {
    console.error('加载系统局域网信息失败', err)
  }
}

const copyLanUrl = async () => {
  if (!systemInfo.value.lan_url) return
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(systemInfo.value.lan_url)
      ElMessage.success(`已复制局域网访问地址: ${systemInfo.value.lan_url}`)
      return
    }
  } catch (e) {}
  ElMessage.info(`局域网访问地址: ${systemInfo.value.lan_url}`)
}

const initAppContent = async () => {
  await Promise.allSettled([
    loadSystemInfo(),
    loadTestUrls(),
    loadProfiles(),
    loadSources()
  ])
}

onMounted(async () => {
  await checkAuthStatus()
  if (!authStatus.value.auth_required || authStatus.value.logged_in) {
    await initAppContent()
  }
})

const loadProfiles = async () => {
  try {
    const res = await api.getProfiles()
    profileList.value = res.data
    if (profileList.value.length > 0 && !currentProfile.value) {
      const pref = profileList.value.find(p => p.name.includes('母本模板'))
      currentProfile.value = pref ? pref.name : profileList.value[0].name
      await loadProfileDetail(currentProfile.value)
    }
  } catch (err) {
    ElMessage.error('加载母本列表失败: ' + (err.response?.data?.detail || err.message))
  }
}

const loadProfileDetail = async (name) => {
  try {
    const res = await api.getProfileDetail(name)
    const data = res.data?.summary || res.data || {}
    currentGroups.value = data.groups || []
    currentProxyCount.value = data.proxy_count || 0
    if (data.test_url) {
      activeTestUrl.value = data.test_url
    }
    loadSavedGroupSelection()
  } catch (err) {
    ElMessage.error('加载母本详情失败')
  }
}

const handleProfileChange = async (val) => {
  await loadProfileDetail(val)
}

const loadSources = async () => {
  try {
    const res = await api.getSources()
    savedSources.value = res.data
  } catch (err) {
    console.error('加载常用源失败', err)
  }
}

const applyQuickSource = (id) => {
  const item = savedSources.value.find(s => s.id === id)
  if (item) {
    fetchUrl.value = item.url
  }
}

const pasteFromClipboard = async () => {
  try {
    if (navigator.clipboard && navigator.clipboard.readText) {
      const text = await navigator.clipboard.readText()
      if (text && text.trim()) {
        fetchUrl.value = text.trim()
        ElMessage.success('已自动粘贴剪贴板链接')
        return
      }
    }
    ElMessage.warning('剪贴板为空或未授权')
  } catch (err) {
    ElMessage.warning('无法自动读取，请使用快捷键 Ctrl+V 粘贴')
  }
}

const handleFetchNodes = async () => {
  if (!fetchUrl.value.trim()) {
    ElMessage.warning('请输入外部订阅链接')
    return
  }
  if (!currentProfile.value) {
    ElMessage.warning('请先在顶部选取母本')
    return
  }



  fetching.value = true
  fetchProgressVisible.value = true
  fetchProgressData.value = {
    percent: 10,
    step: 1,
    msg: '正在连接订阅服务器拉取配置数据...',
    total_raw: 0,
    alive_count: 0,
    filtered_count: 0,
    isDone: false,
    isError: false
  }

  fetchAbortController = new AbortController()

  try {
    const response = await api.fetchNodesStream({
      url: fetchUrl.value.trim(),
      profile_name: currentProfile.value,
      filter_dead: filterDeadOption.value,
      test_url: activeTestUrl.value
    }, fetchAbortController.signal)

    if (!response.ok) {
      throw new Error("HTTP 状态码: " + response.status)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalResult = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()

      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const evt = JSON.parse(line.trim())
          if (evt.type === 'progress') {
            fetchProgressData.value.percent = evt.percent || 10
            fetchProgressData.value.step = evt.step || 1
            fetchProgressData.value.msg = evt.msg || ''
            if (evt.total_raw != null) fetchProgressData.value.total_raw = evt.total_raw
            if (evt.alive_count != null) fetchProgressData.value.alive_count = evt.alive_count
            if (evt.filtered_count != null) fetchProgressData.value.filtered_count = evt.filtered_count
          } else if (evt.type === 'done') {
            finalResult = evt
            fetchProgressData.value.isDone = true
            fetchProgressData.value.percent = 100
            fetchProgressData.value.step = 4
            fetchProgressData.value.msg = evt.msg || '提取完成'
            fetchProgressData.value.total_raw = evt.total_raw
            fetchProgressData.value.alive_count = evt.alive_count
            fetchProgressData.value.filtered_count = evt.filtered_count
          } else if (evt.type === 'error') {
            fetchProgressData.value.isError = true
            fetchProgressData.value.msg = evt.msg || '提取失败'
          }
        } catch (e) {
          console.error('解析流事件错误:', e)
        }
      }
    }

    if (finalResult) {
      totalRawCount.value = finalResult.total_raw || 0
      filteredCount.value = finalResult.filtered_count || 0
      fetchedNodes.value = finalResult.nodes || []
      resolveMissingLocations(fetchedNodes.value)
      newCount.value = finalResult.new_count || 0
      existingCount.value = finalResult.existing_count || 0
      currentGroups.value = finalResult.available_groups || []
      loadSavedGroupSelection()
      hasFetched.value = true

      if (fetchedNodes.value.length === 0) {
        ElMessage.warning('未提取到有效节点（可能全不可达或超时）')
      } else {
        // 提取与 URL Test 完成后 1 秒平滑自动关闭弹窗并进入卡片池
        fetchAutoCloseTimer = setTimeout(() => {
          if (fetchProgressVisible.value && fetchProgressData.value.isDone) {
            finishFetchAndCloseDialog()
          }
        }, 1100)
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') return
    fetchProgressData.value.isError = true
    fetchProgressData.value.msg = err.message || '网络连接异常'
    ElMessage.error('提取失败: ' + err.message)
  } finally {
    fetching.value = false
  }
}


const sortMode = ref('delay') // 'delay' 延迟优先 | 'default' 默认排序

const setSortMode = (mode) => {
  sortMode.value = mode
}

const sortNodesList = (list, mode) => {
  const arr = [...list]
  if (mode === 'default') {
    return arr
  }
  // 延迟优先：URL Test 延迟低的排在前面，超时排在最后
  arr.sort((a, b) => {
    const aDelay = a.delay > 0 ? a.delay : 999999
    const bDelay = b.delay > 0 ? b.delay : 999999
    return aDelay - bDelay
  })
  return arr
}

const filteredNodes = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  let list = fetchedNodes.value
  if (kw) {
    list = list.filter(n => {
      const loc = getNodeLocation(n, ipLocationMap.value)
      return (
        n.name.toLowerCase().includes(kw) ||
        n.type.toLowerCase().includes(kw) ||
        (n.server && n.server.toLowerCase().includes(kw)) ||
        (loc.text && loc.text.toLowerCase().includes(kw)) ||
        (loc.flag && loc.flag.includes(kw))
      )
    })
  }
  return sortNodesList(list, sortMode.value)
})

const isNodeSelected = (id) => selectedNodeIds.value.includes(id)

const toggleNodeSelection = (id) => {
  const idx = selectedNodeIds.value.indexOf(id)
  if (idx > -1) {
    selectedNodeIds.value.splice(idx, 1)
  } else {
    selectedNodeIds.value.push(id)
  }
}

const selectAll = () => {
  selectedNodeIds.value = filteredNodes.value.map(n => n.id)
}

const selectNone = () => {
  selectedNodeIds.value = []
}

const selectOnlyNew = () => {
  selectedNodeIds.value = filteredNodes.value
    .filter(n => !n.is_existing)
    .map(n => n.id)
}

const getDelayClass = (delay) => {
  if (!delay || delay <= 0) return 'delay-dead'
  if (delay < 300) return 'delay-fast'
  if (delay < 800) return 'delay-medium'
  return 'delay-slow'
}

const openImportDrawer = () => {
  if (selectedNodeIds.value.length === 0) {
    ElMessage.warning('请先点击卡片勾选要导入的节点')
    return
  }
  loadSavedGroupSelection()
  importDrawerVisible.value = true
}

const selectAllGroups = () => {
  selectedGroupNames.value = currentGroups.value.map(g => g.name)
  saveCurrentGroupSelection()
}

const clearAllGroups = () => {
  selectedGroupNames.value = []
  saveCurrentGroupSelection()
}

const confirmImport = async () => {
  const nodesToImport = fetchedNodes.value.filter(n => selectedNodeIds.value.includes(n.id))
  if (nodesToImport.length === 0) {
    ElMessage.warning('未选择任何有效节点')
    return
  }

  importing.value = true
  try {
    const res = await api.importNodes({
      profile_name: currentProfile.value,
      nodes: nodesToImport,
      target_groups: selectedGroupNames.value,
      overwrite: overwriteOption.value
    })

    ElMessage.success({
      message: `导入成功！新增 ${res.data.added_count} 个，覆盖更新 ${res.data.updated_count} 个`,
      duration: 5000
    })

    importDrawerVisible.value = false

    // 将已导入节点标记为已存在状态，并清空当前已导入的选中卡片
    const importedIds = new Set(nodesToImport.map(n => n.id))
    fetchedNodes.value.forEach(n => {
      if (importedIds.has(n.id)) {
        n.is_existing = true
      }
    })
    selectedNodeIds.value = []

    await loadProfiles()
    await loadProfileDetail(currentProfile.value)
  } catch (err) {
    ElMessage.error('导入失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    importing.value = false
  }
}

const openProfileModal = () => {
  profileModalVisible.value = true
}

const switchProfile = async (name) => {
  currentProfile.value = name
  await loadProfileDetail(name)
  profileModalVisible.value = false
  ElMessage.success(`已切换母本: ${name}`)
}

const handleDownloadProfile = async () => {
  if (!newProfileUrl.value.trim()) {
    ElMessage.warning('请输入订阅链接')
    return
  }
  downloadingProfile.value = true
  try {
    const res = await api.downloadProfile({
      url: newProfileUrl.value.trim()
    })
    ElMessage.success(res.data.message || '下载并自动识别保存成功！')
    newProfileUrl.value = ''
    await loadProfiles()
    if (res.data.filename) {
      currentProfile.value = res.data.filename
      await loadProfileDetail(res.data.filename)
    }
    profileActiveTab.value = 'list'
  } catch (err) {
    ElMessage.error('下载失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    downloadingProfile.value = false
  }
}

const handleFileChange = (uploadFile) => {
  uploadedFile.value = uploadFile.raw
}

const handleUploadProfile = async () => {
  if (!uploadedFile.value) return
  uploadingProfile.value = true
  try {
    const fd = new FormData()
    fd.append('file', uploadedFile.value)
    const res = await api.uploadProfile(fd)
    ElMessage.success(res.data.message)
    uploadedFile.value = null
    await loadProfiles()
    profileActiveTab.value = 'list'
  } catch (err) {
    ElMessage.error('上传失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    uploadingProfile.value = false
  }
}

const handleCreateDefaultTemplate = async () => {
  try {
    const res = await api.createDefaultProfile(templateProfileName.value)
    ElMessage.success(res.data.message)
    await loadProfiles()
    profileActiveTab.value = 'list'
  } catch (err) {
    ElMessage.error('创建失败: ' + (err.response?.data?.detail || err.message))
  }
}

const handleDeleteProfile = async (name) => {
  try {
    await api.deleteProfile(name)
    ElMessage.success('已删除母本')
    if (currentProfile.value === name) {
      currentProfile.value = ''
    }
    await loadProfiles()
  } catch (err) {
    ElMessage.error('删除失败: ' + (err.response?.data?.detail || err.message))
  }
}

const openProfileEditor = async (name) => {
  editorProfileName.value = name
  editorActiveTab.value = 'groups'
  profileEditorVisible.value = true
  loadingEditorData.value = true
  try {
    const res = await api.getProfileStructure(name)
    editorProxies.value = res.data.proxies || []
    resolveMissingLocations(editorProxies.value)
    editorGroups.value = res.data.proxy_groups || []
    editorRules.value = res.data.rules || []
    editorRulesCount.value = res.data.rules_count || 0
    rawYamlContent.value = res.data.raw_yaml || ''
    selectedEditGroup.value = editorGroups.value[0] || null
    groupSearchQuery.value = ''
    proxySearchQuery.value = ''
    nodesToAddToCurrentGroup.value = []
  } catch (err) {
    ElMessage.error('读取母本配置失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    loadingEditorData.value = false
  }
}

const handleOpenCurrentProfileGroups = () => {
  if (!currentProfile.value) {
    ElMessage.warning('当前未载入任何母本配置')
    return
  }
  openProfileEditor(currentProfile.value)
}

const openYamlEditor = (name) => {
  openProfileEditor(name)
  editorActiveTab.value = 'yaml'
}

const selectGroupForEdit = (grp) => {
  selectedEditGroup.value = grp
  nodesToAddToCurrentGroup.value = []
}

const openAddGroupDialog = () => {
  newGroupForm.value = {
    name: '',
    type: 'select',
    url: 'http://cp.cloudflare.com/generate_204',
    interval: 300,
    tolerance: 50
  }
  newGroupRules.value = []
  newGroupRuleType.value = 'DOMAIN-SUFFIX'
  newGroupRulePayload.value = ''
  addGroupDialogVisible.value = true
}

const addNewGroupRule = () => {
  const payload = newGroupRulePayload.value.trim()
  if (!payload) {
    ElMessage.warning('请输入域名规则内容 (例如: google.com 或 openai)')
    return
  }
  const type = newGroupRuleType.value

  // 1. 检查是否在当前新建列表中已存在
  if (newGroupRules.value.some(r => r.type.toUpperCase() === type.toUpperCase() && r.payload.toLowerCase() === payload.toLowerCase())) {
    ElMessage.warning('当前新建列表中已存在此规则')
    return
  }

  // 2. 检查是否在现有母本策略组中存在
  const conflictRules = []
  editorRules.value.forEach((r, idx) => {
    if (typeof r !== 'string') return
    const parts = r.split(',').map(s => s.trim())
    if (parts.length >= 3 &&
        parts[0].toUpperCase() === type.toUpperCase() &&
        parts[1].toLowerCase() === payload.toLowerCase()) {
      conflictRules.push({ index: idx, group: parts[2], raw: r })
    }
  })

  const doInsertNewRule = () => {
    newGroupRules.value.push({ type, payload })
    newGroupRulePayload.value = ''
    ElMessage.success(`已添加规则: ${type},${payload}`)
  }

  if (conflictRules.length > 0) {
    const otherGroups = [...new Set(conflictRules.map(c => c.group))].join('、')
    ElMessageBox.confirm(
      `规则「${type},${payload}」已存在于策略组「${otherGroups}」中，是否从原策略组删除并关联至此新建策略组？`,
      '规则冲突提示',
      {
        confirmButtonText: '删除原规则并关联',
        cancelButtonText: '取消',
        type: 'warning'
      }
    ).then(() => {
      // 从母本现有规则中删除该旧规则
      editorRules.value = editorRules.value.filter(r => {
        if (typeof r !== 'string') return true
        const p = r.split(',').map(s => s.trim())
        return !(p.length >= 3 &&
                 p[0].toUpperCase() === type.toUpperCase() &&
                 p[1].toLowerCase() === payload.toLowerCase())
      })
      doInsertNewRule()
    }).catch(() => {
      ElMessage.info('已取消操作')
    })
  } else {
    doInsertNewRule()
  }
}

const removeNewGroupRule = (idx) => {
  newGroupRules.value.splice(idx, 1)
}

const confirmAddNewGroup = () => {
  const gName = newGroupForm.value.name.trim()
  if (!gName) {
    ElMessage.warning('请输入策略组名称')
    return
  }
  if (editorGroups.value.some(g => g.name === gName)) {
    ElMessage.warning('策略组名称已存在')
    return
  }
  const newG = {
    name: gName,
    type: newGroupForm.value.type || 'select',
    proxies: []
  }
  if (newG.type !== 'select') {
    newG.url = newGroupForm.value.url || 'http://cp.cloudflare.com/generate_204'
    newG.interval = newGroupForm.value.interval || 300
    newG.tolerance = newGroupForm.value.tolerance || 50
  }
  editorGroups.value.push(newG)
  selectedEditGroup.value = newG

  // 写入新建时配置的域名规则
  if (newGroupRules.value && newGroupRules.value.length > 0) {
    newGroupRules.value.forEach(r => {
      const ruleStr = `${r.type},${r.payload.trim()},${gName}`
      const matchIdx = editorRules.value.findIndex(item => {
        const p = String(item).split(',')[0].trim().toUpperCase()
        return p === 'MATCH' || p === 'GEOIP'
      })
      if (matchIdx !== -1) {
        editorRules.value.splice(matchIdx, 0, ruleStr)
      } else {
        editorRules.value.push(ruleStr)
      }
    })
  }

  addGroupDialogVisible.value = false
  ElMessage.success(`成功创建策略组: ${gName}`)
}

const handleDeleteGroup = (groupName) => {
  editorGroups.value = editorGroups.value.filter(g => g.name !== groupName)
  if (selectedEditGroup.value && selectedEditGroup.value.name === groupName) {
    selectedEditGroup.value = editorGroups.value[0] || null
  }
  // 同步移除专属该策略组的规则
  if (editorRules.value && editorRules.value.length > 0) {
    editorRules.value = editorRules.value.filter(r => {
      if (typeof r !== 'string') return true
      const parts = r.split(',').map(s => s.trim())
      return !(parts.length >= 3 && parts[2] === groupName)
    })
  }
  ElMessage.success(`已删除策略组: ${groupName}`)
}

const handleQuickAddProxiesToGroup = (selectedNames) => {
  if (!selectedEditGroup.value) return
  if (!selectedEditGroup.value.proxies) selectedEditGroup.value.proxies = []
  const currSet = new Set(selectedEditGroup.value.proxies)
  for (const name of selectedNames) {
    if (!currSet.has(name)) {
      selectedEditGroup.value.proxies.push(name)
      currSet.add(name)
    }
  }
  nodesToAddToCurrentGroup.value = []
}

const addAllProxiesToCurrentGroup = () => {
  if (!selectedEditGroup.value) return
  if (!selectedEditGroup.value.proxies) selectedEditGroup.value.proxies = []
  const currSet = new Set(selectedEditGroup.value.proxies)
  let count = 0
  for (const p of editorProxies.value) {
    if (!currSet.has(p.name)) {
      selectedEditGroup.value.proxies.push(p.name)
      currSet.add(p.name)
      count++
    }
  }
  ElMessage.success(`已加入 ${count} 个节点`)
}

const clearCurrentGroupProxies = () => {
  if (!selectedEditGroup.value) return
  selectedEditGroup.value.proxies = []
}

const removeProxyFromCurrentGroup = (pIdx) => {
  if (!selectedEditGroup.value || !selectedEditGroup.value.proxies) return
  selectedEditGroup.value.proxies.splice(pIdx, 1)
}

const moveProxyOrder = (pIdx, direction) => {
  if (!selectedEditGroup.value || !selectedEditGroup.value.proxies) return
  const list = selectedEditGroup.value.proxies
  const targetIdx = pIdx + direction
  if (targetIdx < 0 || targetIdx >= list.length) return
  const temp = list[pIdx]
  list[pIdx] = list[targetIdx]
  list[targetIdx] = temp
}

const getNodeGroupsCount = (proxyName) => {
  return editorGroups.value.filter(g => (g.proxies || []).includes(proxyName)).length
}

const getNodeGroupsTooltip = (proxyName) => {
  const groups = editorGroups.value.filter(g => (g.proxies || []).includes(proxyName)).map(g => g.name)
  return groups.length > 0 ? groups.join(', ') : '未被任何策略组包含'
}

const openAddNodeModal = () => {
  isEditingExistingNode.value = false
  nodeAddMode.value = 'link'
  nodeLinkInput.value = ''
  currentNodeForm.value = {
    name: '',
    type: 'hysteria2',
    server: '',
    port: 443,
    password: '',
    sni: '',
    'skip-cert-verify': true
  }
  editNodeModalVisible.value = true
}

const openEditNodeDetail = (node) => {
  isEditingExistingNode.value = true
  nodeAddMode.value = 'form'
  oldEditingNodeName = node.name || ''
  currentNodeForm.value = JSON.parse(JSON.stringify(node))
  editNodeModalVisible.value = true
}

const confirmSaveNode = async () => {
  if (!isEditingExistingNode.value && nodeAddMode.value === 'link') {
    const rawLink = nodeLinkInput.value.trim()
    if (!rawLink) {
      ElMessage.warning('请输入节点分享链接')
      return
    }
    try {
      const res = await api.parseNodeLink(rawLink)
      const parsedNode = res.data.node
      if (editorProxies.value.some(p => p.name === parsedNode.name)) {
        parsedNode.name = `${parsedNode.name}_${Date.now().toString().slice(-4)}`
      }
      editorProxies.value.unshift(parsedNode)
      editNodeModalVisible.value = false
      ElMessage.success(`成功解析并添加节点: ${parsedNode.name}`)
    } catch (err) {
      ElMessage.error(err.response?.data?.detail || err.message || '解析节点链接失败')
    }
    return
  }

  // 手动表单保存
  const f = currentNodeForm.value
  if (!f.name || !f.name.trim()) {
    ElMessage.warning('请输入节点名称')
    return
  }
  if (!f.server || !f.server.trim()) {
    ElMessage.warning('请输入服务器地址')
    return
  }

  const cleanNode = { ...f, name: f.name.trim(), server: f.server.trim() }
  const portStr = String(f.port || '').trim()
  if (portStr.includes('-') || portStr.includes(',')) {
    cleanNode.ports = portStr
    const firstP = parseInt(portStr.split(/[-,\s]/)[0])
    cleanNode.port = isNaN(firstP) ? 443 : firstP
  } else {
    cleanNode.port = parseInt(portStr) || 443
  }

  if (isEditingExistingNode.value) {
    const idx = editorProxies.value.findIndex(p => p.name === oldEditingNodeName)
    if (idx !== -1) {
      editorProxies.value[idx] = cleanNode
    }
    // 如果重命名了节点，同步更新策略组引用
    if (oldEditingNodeName !== cleanNode.name) {
      editorGroups.value.forEach(g => {
        if (g.proxies) {
          g.proxies = g.proxies.map(p => (p === oldEditingNodeName ? cleanNode.name : p))
        }
      })
    }
    ElMessage.success('节点参数已更新')
  } else {
    if (editorProxies.value.some(p => p.name === cleanNode.name)) {
      ElMessage.warning('节点名称已存在，请使用不同名称')
      return
    }
    editorProxies.value.unshift(cleanNode)
    ElMessage.success('成功添加新节点')
  }
  editNodeModalVisible.value = false
}

const handleDeleteProxy = (nodeName) => {
  editorProxies.value = editorProxies.value.filter(p => p.name !== nodeName)
  // 同步从所有策略组中移除
  editorGroups.value.forEach(g => {
    if (g.proxies) {
      g.proxies = g.proxies.filter(p => p !== nodeName)
    }
  })
  ElMessage.success(`已删除节点: ${nodeName}`)
}

const handleClearAllProxies = () => {
  editorProxies.value = []
  editorGroups.value.forEach(g => {
    if (g.proxies) {
      g.proxies = g.proxies.filter(p => ['DIRECT', 'REJECT'].includes(p) || editorGroups.value.some(grp => grp.name === p))
    }
  })
  ElMessage.success('已清空母本中所有节点')
}

const handleTestAllProfileNodesDelay = async () => {
  if (!editorProxies.value || editorProxies.value.length === 0) {
    ElMessage.info('母本中暂无可测试的节点')
    return
  }
  testingProfileDelays.value = true
  ElMessage.info(`正在通过 Mihomo 内核测定 ${editorProxies.value.length} 个节点的 Unified Delay 真实 RTT 延迟...`)
  try {
    const res = await api.testNodesDelay({ nodes: editorProxies.value })
    const delays = res.data.delays || {}
    editorProxies.value.forEach(p => {
      if (delays[p.name] !== undefined) {
        p.delay = delays[p.name]
      }
    })
    ElMessage.success(`测延迟完成（共测速 ${res.data.total} 个节点）`)
  } catch (err) {
    ElMessage.error('测试延迟失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    testingProfileDelays.value = false
  }
}

const handleTestSingleProfileNodeDelay = async (node) => {
  if (!node) return
  node.delay = 0
  try {
    const res = await api.testNodesDelay({ nodes: [node] })
    const delays = res.data.delays || {}
    if (delays[node.name] !== undefined) {
      node.delay = delays[node.name]
      if (node.delay > 0) {
        ElMessage.success(`「${node.name}」延迟: ${node.delay} ms`)
      } else {
        ElMessage.warning(`「${node.name}」连接超时`)
      }
    }
  } catch (err) {
    ElMessage.error('测试延迟失败')
    node.delay = -1
  }
}

const switchEditorTab = async (tab) => {
  if (tab === editorActiveTab.value) return

  // 1. 如果切向 YAML 源码：先从当前可视化数据生成最新 YAML 预览
  if (tab === 'yaml') {
    loadingEditorData.value = true
    try {
      const res = await api.previewProfileYaml(editorProfileName.value, {
        proxies: editorProxies.value,
        proxy_groups: editorGroups.value,
        rules: editorRules.value
      })
      rawYamlContent.value = res.data.yaml
      editorActiveTab.value = 'yaml'
    } catch (err) {
      ElMessage.error('生成 YAML 预览失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      loadingEditorData.value = false
    }
    return
  }

  // 2. 如果从 YAML 源码切回 可视化面板：解析源码中的节点和策略组
  if (editorActiveTab.value === 'yaml') {
    loadingEditorData.value = true
    try {
      const res = await api.parseYamlText(rawYamlContent.value)
      editorProxies.value = res.data.proxies || []
    resolveMissingLocations(editorProxies.value)
      editorGroups.value = res.data.proxy_groups || []
      if (res.data.rules) editorRules.value = res.data.rules
      if (!selectedEditGroup.value || !editorGroups.value.some(g => g.name === selectedEditGroup.value.name)) {
        selectedEditGroup.value = editorGroups.value[0] || null
      }
      editorActiveTab.value = tab
    } catch (err) {
      ElMessage.error('YAML 语法存在错误，无法解析为可视化结构: ' + (err.response?.data?.detail || err.message))
      return
    } finally {
      loadingEditorData.value = false
    }
    return
  }

  editorActiveTab.value = tab
}

const handleSaveEditorData = async () => {
  savingEditor.value = true
  try {
    if (editorActiveTab.value === 'yaml') {
      await api.saveRawYaml(editorProfileName.value, rawYamlContent.value)
    } else {
      await api.saveProfileStructure(editorProfileName.value, {
        proxies: editorProxies.value,
        proxy_groups: editorGroups.value,
        rules: editorRules.value
      })
    }
    ElMessage.success('母本配置保存成功，已自动生成快照备份！')
    profileEditorVisible.value = false
    await loadProfiles()
    await loadProfileDetail(editorProfileName.value)
  } catch (err) {
    ElMessage.error('保存失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    savingEditor.value = false
  }
}

const openBackups = async (name) => {
  backupProfileName.value = name
  try {
    const res = await api.getBackups(name)
    backupsList.value = res.data
    backupDrawerVisible.value = true
  } catch (err) {
    ElMessage.error('获取备份列表失败')
  }
}

const handleRestoreBackup = async (filename) => {
  try {
    await api.restoreBackup(backupProfileName.value, filename)
    ElMessage.success('恢复快照成功')
    backupDrawerVisible.value = false
    await loadProfiles()
    await loadProfileDetail(backupProfileName.value)
  } catch (err) {
    ElMessage.error('恢复失败: ' + (err.response?.data?.detail || err.message))
  }
}

const editingSourceId = ref(null)

const openSourceModal = () => {
  sourceModalVisible.value = true
}

const openAddSourceDialog = () => {
  editingSourceId.value = null
  sourceForm.value = { name: '', url: '', notes: '' }
  addSourceDialogVisible.value = true
}

const openEditSourceDialog = (row) => {
  editingSourceId.value = row.id
  sourceForm.value = {
    name: row.name || '',
    url: row.url || '',
    notes: row.notes || ''
  }
  addSourceDialogVisible.value = true
}

const handleSaveSource = async () => {
  if (!sourceForm.value.name || !sourceForm.value.url) {
    ElMessage.warning('请填写名称与链接')
    return
  }
  try {
    if (editingSourceId.value) {
      await api.updateSource(editingSourceId.value, sourceForm.value)
      ElMessage.success('订阅源已更新')
    } else {
      await api.addSource(sourceForm.value)
      ElMessage.success('添加成功')
    }
    addSourceDialogVisible.value = false
    await loadSources()
  } catch (err) {
    ElMessage.error(editingSourceId.value ? '更新失败' : '保存失败')
  }
}

const handleDeleteSource = async (id) => {
  try {
    await api.deleteSource(id)
    ElMessage.success('已删除订阅源')
    await loadSources()
  } catch (err) {
    ElMessage.error('删除失败')
  }
}
</script>

<style scoped>
/* ================= 3X-UI 纯净科技暗黑风格 ================= */
.xui-app-container {
  min-height: 100vh;
  background-color: #1a1b1f; /* 3X-UI 深邃纯正暗黑蓝 */
  color: #c9d1d9;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  display: flex;
  flex-direction: column;
}

/* 顶部导航条 (已删除 3X 标，高度由 54px 调宽至 60px，间距舒展) */
.xui-top-header {
  height: 60px;
  background-color: #23252b;
  border-bottom: 1px solid #2a2d36;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  position: sticky;
  top: 0;
  z-index: 50;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
}

.header-brand-section {
  display: flex;
  align-items: center;
  gap: 20px;
}

.status-pill-3x {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #2a2d36;
  border: 1px solid #323642;
  border-radius: 20px;
  padding: 4px 14px;
  font-size: 13px;
}

.status-live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background-color: #3fb950;
  box-shadow: 0 0 8px #3fb950;
}

.status-tip-text {
  color: #8b949e;
}

.status-name-text {
  color: #f0f6fc;
  font-weight: 600;
}

.profile-select-inline {
  display: flex;
  align-items: center;
  gap: 10px;
}

.inline-label {
  font-size: 13px;
  color: #8b949e;
}

.select-row-flex {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.select-sub-info {
  font-size: 11px;
  color: #8b949e;
}

.header-action-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-nav-btns-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 按钮规范 (3X-UI 经典暗色/深蓝科技) */
.xui-nav-btn {
  background: #2a2d36;
  border: 1px solid #323642;
  color: #cbd5e1;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  padding: 6px 14px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.xui-nav-btn:hover {
  background: #2f333e;
  border-color: #3b82f6;
  color: #ffffff;
}

.xui-std-btn {
  background: #2a2d36;
  border: 1px solid #323642;
  color: #cbd5e1;
  border-radius: 6px;
  font-size: 13px;
  padding: 7px 16px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.xui-std-btn:hover {
  background: #2f333e;
  color: #ffffff;
}

.xui-primary-btn {
  background: linear-gradient(135deg, #1f6feb, #1a56db);
  border: 1px solid #388bfd;
  color: #ffffff;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  padding: 7px 18px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.xui-primary-btn:hover:not(:disabled) {
  background: #2563eb;
  box-shadow: 0 0 12px rgba(37, 99, 235, 0.45);
}

.xui-primary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 主工作区内容 (加大垂直留白，呼吸感强) */
.xui-main-content {
  flex: 1;
  padding: 28px 36px;
  max-width: 1600px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 22px; /* 板块间距拉大，不再局促 */
}

/* 顶部指标卡片 */
/* 工作区左右布局容器：始终保持伸展对齐，确保右侧最小高度与左侧严格平齐 */
.xui-workspace-split {
  display: flex;
  align-items: stretch;
  gap: 20px;
  width: 100%;
}

/* 左侧指标卡片侧栏 */
.xui-metrics-sidebar {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: sticky;
  top: 20px;
  align-self: flex-start; /* 正常有大量卡片时自然吸顶浮动 */
}

.xui-metrics-sidebar.is-empty-nodes {
  position: static;
  align-self: stretch;
  height: auto;
}

/* 未添加节点卡片时，左侧 4 张卡片平分整体高度，整体高度严格等于右侧 */
.xui-metrics-sidebar.is-empty-nodes .xui-metric-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

/* 右侧节点池主工作区 */
.xui-pool-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-self: stretch;
}

/* 无论是否添加节点、节点数量多少，右侧卡片面板最小高度均与左边 4 张卡片平齐 (~430px) */
.xui-pool-main .xui-card-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 430px;
  box-sizing: border-box;
}

.xui-pool-main .xui-card-panel .panel-inner-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.xui-pool-main.is-empty-nodes .xui-card-panel .panel-inner-body {
  justify-content: center;
}

.xui-metric-box.clickable-metric {
  cursor: pointer;
  transition: border-color 0.2s ease, background-color 0.2s ease, transform 0.15s ease;
}

.xui-metric-box.clickable-metric:hover {
  border-color: #58a6ff;
  background-color: #262932;
  transform: translateY(-1px);
}

@media (max-width: 1080px) {
  .xui-workspace-split {
    flex-direction: column;
  }
  .xui-metrics-sidebar {
    width: 100%;
    position: static;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .xui-metrics-sidebar {
    grid-template-columns: 1fr;
  }
}

.xui-metric-box {
  background-color: #23252b;
  border: 1px solid #2a2d36;
  border-radius: 10px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 88px;
  transition: border-color 0.2s ease;
}

.xui-metric-box:hover {
  border-color: #3a3f4d;
}

.metric-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.m-title {
  font-size: 13px;
  color: #8b949e;
  font-weight: 500;
}

.m-val {
  font-size: 24px;
  font-weight: 700;
  color: #f0f6fc;
  margin: 4px 0;
}

.m-unit {
  font-size: 13px;
  font-weight: normal;
  color: #8b949e;
}

.m-val.text-green {
  color: #3fb950;
}

.m-val.text-blue {
  color: #58a6ff;
}

.m-sub {
  font-size: 12px;
  color: #8b949e;
}

/* 3X-UI 风格卡片面板 */
.xui-card-panel {
  background-color: #23252b;
  border: 1px solid #2a2d36;
  border-radius: 10px;
  overflow: hidden;
}

.test-url-option {
  display: flex;
  flex-direction: column;
  padding: 3px 0;
  line-height: 1.3;
}
.test-url-option .opt-name {
  font-size: 13px;
  font-weight: 500;
  color: #f0f6fc;
}
.test-url-option .opt-desc {
  font-size: 11px;
  color: #8b949e;
}
.panel-head-bar {
  padding: 14px 22px;
  border-bottom: 1px solid #2a2d36;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #282b33;
}

.panel-head-title {
  font-size: 14px;
  font-weight: 600;
  color: #f0f6fc;
}

.panel-head-title-flex {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #f0f6fc;
}

.panel-num-pill {
  background: #2d313c;
  color: #58a6ff;
  border: 1px solid #353a47;
  font-size: 11px;
  font-weight: 700;
  padding: 1px 8px;
  border-radius: 10px;
}

.panel-head-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.quick-src-label {
  font-size: 13px;
  color: #8b949e;
  margin-right: 6px;
}

.panel-inner-body {
  padding: 20px 22px;
}

.fetch-action-bar {
  display: flex;
  gap: 12px;
}

.fetch-input-field {
  flex: 1;
}

.panel-note-line {
  margin-top: 12px;
  font-size: 12px;
  color: #8b949e;
  display: flex;
  align-items: center;
  gap: 6px;
}

.note-dot {
  width: 5px;
  height: 5px;
  background: #58a6ff;
  border-radius: 50%;
}

.xui-mini-btn-group {
  display: flex;
  background: #1a1b1f;
  border: 1px solid #2e323b;
  border-radius: 6px;
  padding: 2px;
}

.m-btn {
  background: transparent;
  border: none;
  color: #8b949e;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.m-btn:hover {
  color: #f0f6fc;
  background: #2e323b;
}

.m-btn.m-btn-highlight {
  color: #3fb950;
}

/* ================= 3X-UI 节点网格卡片 (高级沉稳配色) ================= */
.xui-nodes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(245px, 1fr));
  gap: 12px;
}

.xui-node-card {
  background-color: #1e2026; /* 沉静石墨炭灰 */
  border: 1px solid #2d3039;
  border-radius: 8px;
  padding: 11px 13px;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
  user-select: none;
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 62px;
}

.xui-node-card:hover {
  border-color: #3f4450;
  background-color: #242730;
}

/* 选中态：完全不需要外部描边，石墨灰微提亮，仅靠右上角蓝圈勾选识别 */
.xui-node-card.card-selected {
  background-color: #242731; /* 柔和深石墨微提亮，与卡片沉稳融合 */
  border-color: #2d3039;    /* 彻底移除外部描边，保持与未选卡片一致的深灰底线 */
  box-shadow: none !important;
}

.xui-node-card.card-selected:hover {
  border-color: #3f4450;
  background-color: #282c37;
}

.m-btn.m-btn-active {
  color: #ffffff;
  background: #2e323d;
  font-weight: 600;
}


.node-title-wrapper {
  display: flex;
  align-items: center;
  gap: 7px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.node-card-flag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  line-height: 1;
  background: none !important;
  border: none !important;
  padding: 0 !important;
}

.country-flag-svg {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 19px;
  height: 13px;
  border-radius: 2px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
  flex-shrink: 0;
  vertical-align: middle;
}

.country-flag-svg svg {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.node-card-top-line {
  display: flex;
  min-width: 0;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.node-title-main {
  font-size: 13px;
  font-weight: 500;
  color: #e6edf3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.xui-node-card.card-selected .node-title-main {
  color: #ffffff;
  font-weight: 600;
}

/* 仅在母本已有时展示暗橙微标 */
.tag-in-master {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(210, 153, 34, 0.15);
  color: #d29922;
  border: 1px solid rgba(210, 153, 34, 0.3);
  flex-shrink: 0;
}

.node-card-bottom-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.node-proto-label {
  font-size: 11px;
  color: #8b949e;
  font-family: Consolas, Monaco, monospace;
}

.xui-node-card.card-selected .node-proto-label {
  color: #8b949e;
}

.node-metrics-tags {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* 速度标签 (无边框硬线，4px微圆角，与卡片沉稳融合) */
.node-delay-pill {
  font-size: 11px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 4px;
  border: none;
  line-height: 1.4;
  white-space: nowrap;
}

.delay-fast {
  background: rgba(34, 197, 94, 0.08);
  color: #4ade80;
}

.delay-medium {
  background: rgba(245, 158, 11, 0.08);
  color: #fbbf24;
}

.delay-slow {
  background: rgba(239, 68, 68, 0.08);
  color: #f87171;
}

.delay-dead {
  background: rgba(148, 163, 184, 0.08);
  color: #94a3b8;
}

/* 选中角标 Check (沉稳对勾) */
.card-top-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

/* 内嵌式复选圈 (不溢出卡片，未选低调，选中自然) */
.circle-check-badge {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background-color: #2563eb;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.filter-empty-tip {
  text-align: center;
  padding: 40px 0;
  color: #8b949e;
  font-size: 13px;
}

.xui-empty-guide {
  margin-top: 0;
  flex: 1;
  min-height: 430px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  padding: 40px 20px;
  background: #23252b;
  border: 1px dashed #2e323b;
  border-radius: 10px;
  text-align: center;
}

.guide-circle-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #2a2d36;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}

.guide-title {
  margin: 0 0 8px;
  font-size: 15px;
  color: #f0f6fc;
}

.guide-desc {
  margin: 0;
  font-size: 13px;
  color: #8b949e;
}

/* ================= 抽屉与弹窗深度定制 (消除割裂感) ================= */
.drawer-layout-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.drawer-target-card {
  background: #1f2127;
  border: 1px solid #2e323b;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.target-title {
  font-size: 13px;
  color: #f0f6fc;
}

.target-num {
  font-size: 12px;
  color: #58a6ff;
}

.drawer-form-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-header-row {
  font-size: 13px;
  font-weight: 600;
  color: #cbd5e1;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-fast-links {
  display: flex;
  gap: 8px;
}

.fast-link {
  background: transparent;
  border: none;
  color: #58a6ff;
  font-size: 12px;
  cursor: pointer;
}

.fast-link:hover {
  text-decoration: underline;
}

.groups-select-scroll {
  background: #1a1b1f;
  border: 1px solid #2e323b;
  border-radius: 8px;
  padding: 12px;
  max-height: 250px;
  overflow-y: auto;
}

.checkbox-col-stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-row-item {
  padding: 2px 0;
}

.g-name-text {
  color: #f0f6fc;
  font-weight: 500;
  margin-right: 6px;
}

.g-type-text {
  color: #8b949e;
  font-size: 11px;
}

/* 抽屉单选框选项组严格左对齐 */
.radio-vertical-stack {
  display: flex !important;
  flex-direction: column !important;
  align-items: flex-start !important;
  justify-content: flex-start !important;
  gap: 12px !important;
  width: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
}

:deep(.radio-vertical-stack .el-radio),
.radio-vertical-stack .el-radio {
  display: flex !important;
  align-items: flex-start !important;
  justify-content: flex-start !important;
  width: 100% !important;
  height: auto !important;
  margin: 0 !important;
  padding: 4px 0 !important;
  white-space: normal !important;
  cursor: pointer;
}

:deep(.radio-vertical-stack .el-radio .el-radio__input),
.radio-vertical-stack .el-radio .el-radio__input {
  margin-top: 2px !important;
  flex-shrink: 0 !important;
}

:deep(.radio-vertical-stack .el-radio .el-radio__label),
.radio-vertical-stack .el-radio .el-radio__label {
  padding-left: 8px !important;
  display: flex !important;
  flex-direction: column !important;
  align-items: flex-start !important;
  text-align: left !important;
  white-space: normal !important;
  flex: 1 !important;
}

.radio-main-txt {
  font-weight: 600;
  font-size: 13px;
  color: #f0f6fc;
  display: block;
  text-align: left;
  line-height: 1.4;
}

.radio-sub-txt {
  font-size: 12px;
  color: #8b949e;
  display: block;
  margin-top: 2px;
  line-height: 1.4;
  text-align: left;
}

.safe-callout-card {
  font-size: 12px;
  color: #8b949e;
  background: #1f2127;
  padding: 12px 14px;
  border-radius: 6px;
  border-left: 3px solid #d29922;
  line-height: 1.6;
}

.safe-callout-card code {
  color: #58a6ff;
}

.drawer-footer-row {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.tbl-name-label.is-active {
  color: #58a6ff;
  font-weight: 700;
}

/* 桌面端表格 vs 移动端卡片式自适应 */
.desktop-only-table {
  display: block;
}

.mobile-only-cards {
  display: none !important;
}

.profile-mobile-card-list {
  display: none;
  flex-direction: column;
  gap: 10px;
}

.profile-m-item {
  background: #23252b;
  border: 1px solid #30333d;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.2s ease;
}

.profile-m-item.is-current {
  border-color: #2563eb;
  background: rgba(37, 99, 235, 0.06);
}

.pmi-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.pmi-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: #f1f5f9;
  font-size: 14px;
  min-width: 0;
  flex: 1;
}

.pmi-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pmi-meta-tags {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.pmi-tag {
  background: #1a1b1f;
  border: 1px solid #333842;
  color: #94a3b8;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
}

.pmi-time-row {
  font-size: 11px;
  color: #64748b;
}

.pmi-actions-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding-top: 6px;
  border-top: 1px dashed rgba(255, 255, 255, 0.08);
}

.pmi-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 5px 8px;
  font-size: 12px;
  border-radius: 5px;
  border: 1px solid #333842;
  background: #2a2d36;
  color: #cbd5e1;
  cursor: pointer;
  transition: all 0.15s ease;
  flex: 1 1 auto;
  min-width: 50px;
  height: 32px;
  box-sizing: border-box;
}

.pmi-btn-edit {
  background: #2563eb !important;
  border-color: #3b82f6 !important;
  color: #ffffff !important;
  font-weight: 600;
  box-shadow: 0 0 8px rgba(37, 99, 235, 0.35);
  flex: 1.2 1 auto;
}

.pmi-btn-edit:hover {
  background: #1d4ed8 !important;
}

.pmi-btn-switch.active {
  background: rgba(16, 185, 129, 0.15);
  border-color: rgba(16, 185, 129, 0.4);
  color: #34d399;
}

.pmi-btn-danger:hover {
  background: rgba(239, 68, 68, 0.15);
  border-color: #ef4444;
  color: #f87171;
}

/* 常用源手机端卡片 */
.source-mobile-card-list {
  display: none;
  flex-direction: column;
  gap: 10px;
}

.source-m-item {
  background: #23252b;
  border: 1px solid #30333d;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.smi-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.smi-name {
  font-weight: 600;
  color: #f1f5f9;
  font-size: 13px;
}

.smi-notes {
  font-size: 11px;
  color: #94a3b8;
  background: #1a1b1f;
  padding: 2px 6px;
  border-radius: 4px;
}

.smi-url {
  font-size: 11px;
  color: #64748b;
  word-break: break-all;
  line-height: 1.4;
}

.smi-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
}


.row-actions-flex {
  display: flex !important;
  align-items: center !important;
  justify-content: flex-end !important;
  gap: 8px !important;
  white-space: nowrap !important;
}

.row-actions-flex .el-button {
  margin: 0 !important;
  padding: 0 3px !important;
  font-size: 13px !important;
}

.curr-badge {
  font-size: 10px;
  background: #1f6feb;
  color: #ffffff;
  padding: 1px 5px;
  border-radius: 3px;
  margin-left: 6px;
}

.muted-text {
  color: #8b949e;
  font-size: 12px;
}

.backup-box-row {
  background: #1f2127;
  border: 1px solid #2e323b;
  border-radius: 6px;
  padding: 10px 14px;
}

.b-details {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.b-title {
  font-family: Consolas, Monaco, monospace;
  color: #f0f6fc;
}

.b-filesize {
  color: #8b949e;
}

.upload-3x-panel {
  width: 100%;
}

/* ================= 提取进度弹窗 (3X-UI 暗黑高质感) ================= */
.fetch-progress-body {
  padding: 6px 0;
}

.progress-main-status {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #1e2026;
  border: 1px solid #2d3039;
  border-radius: 8px;
  padding: 16px 18px;
  margin-bottom: 20px;
}

.status-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #252831;
  flex-shrink: 0;
}

.status-texts {
  flex: 1;
  min-width: 0;
}

.status-primary-title {
  font-size: 15px;
  font-weight: 600;
  color: #f0f6fc;
  margin-bottom: 4px;
}

.status-sub-msg {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 140px;
  overflow-y: auto;
}

/* 进度条 */
.progress-bar-container {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 20px;
}

.progress-track {
  flex: 1;
  height: 8px;
  background: #1a1b1f;
  border-radius: 4px;
  overflow: hidden;
  border: 1px solid #2e323b;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.progress-fill.fill-active {
  background: linear-gradient(90deg, #2563eb, #38bdf8);
}

.progress-fill.fill-success {
  background: #22c55e;
}

.progress-fill.fill-error {
  background: #ef4444;
}

.progress-percent-label {
  font-size: 13px;
  font-weight: 600;
  font-family: Consolas, Monaco, monospace;
  color: #cbd5e1;
  min-width: 42px;
  text-align: right;
}

/* 实时数据统计卡片 */
.progress-stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 20px;
}

.stat-mini-card {
  background: #1e2026;
  border: 1px solid #2d3039;
  border-radius: 6px;
  padding: 10px 12px;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-mini-card .stat-num {
  font-size: 18px;
  font-weight: 700;
  color: #f0f6fc;
  font-family: Consolas, Monaco, monospace;
}

.stat-mini-card .stat-lbl {
  font-size: 11px;
  color: #8b949e;
}

/* 步骤指示列表 */
.progress-steps-list {
  background: #1e2026;
  border: 1px solid #2d3039;
  border-radius: 8px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.p-step-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #64748b;
  transition: color 0.2s ease;
}

.step-indicator {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  background: #252831;
  color: #64748b;
  border: 1px solid #333842;
  flex-shrink: 0;
}

.p-step-item.step-done {
  color: #cbd5e1;
}

.p-step-item.step-done .step-indicator {
  background: #14532d;
  color: #4ade80;
  border-color: #22c55e;
}

.p-step-item.step-active {
  color: #f0f6fc;
  font-weight: 500;
}

.p-step-item.step-active .step-indicator {
  background: #1e3a8a;
  color: #38bdf8;
  border-color: #3b82f6;
  animation: pulse-step 1.2s infinite;
}

.p-step-item.step-error {
  color: #f87171;
}

.p-step-item.step-error .step-indicator {
  background: #7f1d1d;
  color: #f87171;
  border-color: #ef4444;
}

@keyframes pulse-step {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.dialog-footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.lan-pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #1a1b1f;
  border: 1px solid #2e323b;
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 12px;
  color: #8b949e;
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

.lan-pill-btn:hover {
  background: #252831;
  border-color: #3f4450;
  color: #cbd5e1;
}

.lan-live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3b82f6;
  box-shadow: 0 0 6px rgba(59, 130, 246, 0.5);
}

.lan-text {
  font-family: Consolas, Monaco, monospace;
  font-size: 11px;
}

/* ================= 远程上传弹窗 (SMB / FTP / WebDAV) ================= */
.remote-dialog-body {
  padding: 4px 0;
}

.remote-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  background: #1e2026;
  border: 1px solid #2d3039;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

.remote-target-select-row,
.remote-preset-select-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.r-label {
  font-size: 12px;
  color: #8b949e;
}

.protocol-tabs-wrap {
  margin-bottom: 16px;
}

.protocol-tabs-group {
  display: flex;
  background: #1a1b1f;
  border: 1px solid #2e323b;
  border-radius: 6px;
  padding: 3px;
  gap: 4px;
}

.p-tab-btn {
  flex: 1;
  background: transparent;
  border: none;
  color: #8b949e;
  font-size: 12px;
  font-weight: 500;
  padding: 6px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.p-tab-btn:hover {
  color: #f0f6fc;
  background: #252831;
}

.p-tab-btn.active {
  color: #ffffff;
  background: #2563eb;
  font-weight: 600;
}

.remote-upload-form .el-form-item {
  margin-bottom: 14px;
}

.form-cols-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-cols-2-1 {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 12px;
}

.form-cols-3 {
  display: grid;
  grid-template-columns: 1fr 1fr 90px;
  gap: 12px;
}

.form-tip-line {
  font-size: 11px;
  color: #8b949e;
  margin-top: -6px;
  margin-bottom: 12px;
  line-height: 1.4;
}

.remote-options-box {
  background: #1e2026;
  border: 1px solid #2d3039;
  border-radius: 6px;
  padding: 10px 14px;
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.opt-row {
  display: flex;
  align-items: center;
}

.save-target-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}

.opt-txt {
  font-size: 12px;
  color: #cbd5e1;
}


/* ================= 移动端 / 手机端 UI 适配规范 (Scoped) ================= */
@media (max-width: 768px) {
  .xui-app-container {
    overflow-x: hidden !important;
    width: 100% !important;
    max-width: 100vw !important;
  }

  .desktop-only-table {
    display: none !important;
  }

  .mobile-only-cards {
    display: flex !important;
  }

  /* 弹窗中的 tabs 在手机端紧凑展示，减少左右箭头占位 */
  .xui-custom-tabs .el-tabs__item {
    padding: 0 8px !important;
    font-size: 12.5px !important;
  }

  .xui-custom-tabs .el-tabs__header {
    margin-bottom: 12px !important;
  }

  /* 顶部导航栏自适应堆叠 */
  .xui-top-header {
    height: auto !important;
    min-height: 54px;
    padding: 10px 14px !important;
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 10px !important;
  }

  .header-brand-section {
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 8px !important;
    width: 100% !important;
  }

  .status-pill-3x {
    width: 100% !important;
    box-sizing: border-box !important;
    justify-content: center !important;
    font-size: 12px !important;
    padding: 4px 10px !important;
  }

  .profile-select-inline {
    width: 100% !important;
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
  }

  .profile-select-inline .inline-label {
    white-space: nowrap !important;
    font-size: 12px !important;
  }

  .profile-select-inline .el-select {
    flex: 1 !important;
    width: auto !important;
  }

  .header-action-section {
    width: 100% !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 8px !important;
  }

  .header-action-section .lan-pill-btn {
    width: 100% !important;
    justify-content: center !important;
    box-sizing: border-box !important;
  }

  /* 顶部操作按钮保持单行水平排布 */
  .header-nav-btns-row {
    width: 100% !important;
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 8px !important;
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
    -webkit-overflow-scrolling: touch !important;
    scrollbar-width: none !important;
  }

  .header-nav-btns-row::-webkit-scrollbar {
    display: none !important;
  }

  .header-nav-btns-row .xui-nav-btn {
    flex: 1 1 0 !important;
    min-width: fit-content !important;
    justify-content: center !important;
    padding: 8px 6px !important;
    font-size: 12px !important;
    white-space: nowrap !important;
    box-sizing: border-box !important;
    height: 38px !important;
  }

  /* 主工作区内边距微调 */
  .xui-main-content {
    padding: 12px 10px !important;
    gap: 14px !important;
  }

  /* 工作区分割与指标栏 (手机端无需展示4张指标卡片) */
  .xui-workspace-split {
    display: block !important;
  }

  .xui-metrics-sidebar {
    display: none !important;
  }

  /* 订阅提取控制卡片 */
  .panel-head-bar {
    padding: 12px 14px !important;
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 10px !important;
  }

  .panel-head-title-flex {
    flex-wrap: wrap !important;
    gap: 6px !important;
  }

  .panel-head-right {
    width: 100% !important;
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 8px !important;
  }

  .test-url-selector-wrap {
    width: 100% !important;
    display: flex !important;
    align-items: center !important;
  }

  .test-url-selector-wrap .el-select {
    flex: 1 !important;
    width: auto !important;
  }

  .panel-head-right .xui-primary-btn {
    width: 100% !important;
    justify-content: center !important;
  }

  .panel-inner-body {
    padding: 14px 12px !important;
  }

  .fetch-action-bar {
    flex-direction: column !important;
    gap: 8px !important;
  }

  .fetch-input-field {
    width: 100% !important;
  }

  .fetch-action-bar .xui-std-btn,
  .fetch-action-bar .xui-primary-btn {
    width: 100% !important;
    justify-content: center !important;
    height: 38px !important;
  }

  .panel-note-line {
    flex-direction: column !important;
    align-items: flex-start !important;
    gap: 6px !important;
  }

  .quick-sources-bar {
    width: 100% !important;
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
    -webkit-overflow-scrolling: touch !important;
    padding-bottom: 6px !important;
  }

  .quick-sources-bar .src-chip-btn {
    flex-shrink: 0 !important;
  }

  /* 节点池操作与过滤 */
  .panel-head-actions {
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 8px !important;
    width: 100% !important;
  }

  .panel-head-actions .el-input {
    width: 100% !important;
  }

  .xui-mini-btn-group {
    width: 100% !important;
    display: flex !important;
  }

  .xui-mini-btn-group .m-btn {
    flex: 1 !important;
    text-align: center !important;
    padding: 5px 4px !important;
    font-size: 11px !important;
  }

  .panel-head-actions .xui-primary-btn {
    width: 100% !important;
    justify-content: center !important;
  }

  .protocol-tabs-group {
    width: 100% !important;
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
    -webkit-overflow-scrolling: touch !important;
    padding-bottom: 6px !important;
  }

  .protocol-tabs-group .p-tab-btn {
    flex-shrink: 0 !important;
    padding: 5px 10px !important;
    font-size: 12px !important;
  }

  /* 节点卡片网格单列流动 */
  .xui-nodes-grid {
    grid-template-columns: 1fr !important;
    gap: 10px !important;
  }

  .xui-node-card {
    padding: 12px 12px !important;
  }
}

@media (max-width: 480px) {
  .header-nav-btns-row {
    gap: 6px !important;
  }

  .header-nav-btns-row .xui-nav-btn {
    padding: 7px 4px !important;
    font-size: 11.5px !important;
    gap: 4px !important;
  }
}

.remote-footer-flex {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

/* 策略组关联域名规则样式 */
.group-rules-section {
  margin-top: 14px;
  padding: 12px;
  background-color: #16181d;
  border: 1px solid #282d38;
  border-radius: 8px;
  box-sizing: border-box;
  width: 100%;
}

.rules-section-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 10px;
}

.rules-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
}

.rules-section-tip {
  font-size: 11px;
  color: #64748b;
}

.rules-list-container {
  max-height: 140px;
  overflow-y: auto;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
  padding: 6px;
  background-color: #121316;
  border-radius: 6px;
  border: 1px solid #1f232b;
  min-height: 42px;
  align-items: center;
  box-sizing: border-box;
  width: 100%;
}

.rules-empty-note {
  font-size: 12px;
  color: #475569;
  padding: 10px 12px;
  box-sizing: border-box;
  width: 100%;
  text-align: center;
  background-color: #121316;
  border-radius: 6px;
  border: 1px dashed #282d38;
  margin-bottom: 10px;
}

.rule-item-chip {
  display: inline-flex;
  align-items: center;
  background-color: #1c2128;
  border: 1px solid #30363d;
  border-radius: 4px;
  padding: 2px 6px;
  gap: 6px;
  font-size: 12px;
}

.rule-type-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 3px;
  background-color: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  font-family: Consolas, Monaco, monospace;
}

.rule-payload-text {
  color: #cbd5e1;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: Consolas, Monaco, monospace;
}

.rule-del-btn {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0 2px;
  font-size: 14px;
  line-height: 1;
  transition: color 0.15s ease;
}

.rule-del-btn:hover {
  color: #ef4444;
}

.rule-add-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 策略组卡片整卡拖拽样式 */
.z-group-card.is-card-dragging {
  opacity: 0.45;
  border: 1px dashed #3b82f6 !important;
  transform: scale(0.985);
}

.z-group-card.is-card-drop-target {
  border-color: #3b82f6 !important;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.35) !important;
}

.z-card-drag-handle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  color: #64748b;
  cursor: grab;
  user-select: none;
  margin-right: 6px;
  padding: 0 3px;
  border-radius: 4px;
  transition: all 0.15s ease;
}

.z-card-drag-handle:hover {
  color: #60a5fa;
  background-color: rgba(96, 165, 250, 0.15);
}

.z-card-drag-handle:active {
  cursor: grabbing;
}

/* 未测与测速中延迟状态 */
.delay-none {
  background-color: rgba(148, 163, 184, 0.1) !important;
  color: #64748b !important;
  border-color: rgba(148, 163, 184, 0.2) !important;
  cursor: pointer;
}

.delay-testing {
  background-color: rgba(59, 130, 246, 0.15) !important;
  color: #60a5fa !important;
  border-color: rgba(59, 130, 246, 0.3) !important;
  cursor: wait;
}

</style>

<!-- 全局重载 Element Plus 弹窗与表格，彻底消除图3图4的割裂感 -->
<style>
/* ================= 全局 3X-UI 暗黑科技滚动条规范 (告别原生浅灰大粗条) ================= */
* {
  scrollbar-width: thin;
  scrollbar-color: #2b303d rgba(0, 0, 0, 0.2);
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb {
  background: #2c3240;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.04);
  transition: all 0.2s ease;
}

::-webkit-scrollbar-thumb:hover {
  background: #2563eb;
  box-shadow: 0 0 10px rgba(37, 99, 235, 0.6);
}

::-webkit-scrollbar-corner {
  background: transparent;
}

/* 弹窗容器暗黑化 */
.el-dialog {
  background-color: #23252b !important;
  border: 1px solid #2e323b !important;
  border-radius: 12px !important;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7) !important;
}

.el-dialog__header {
  border-bottom: 1px solid #2a2d36 !important;
  padding: 16px 22px !important;
  margin-right: 0 !important;
}

.el-dialog__title {
  color: #f0f6fc !important;
  font-size: 15px !important;
  font-weight: 600 !important;
}

.el-dialog__body {
  padding: 20px 22px !important;
  color: #cbd5e1 !important;
}

.el-dialog__footer {
  border-top: 1px solid #2a2d36 !important;
  padding: 14px 22px !important;
}

/* 抽屉容器暗黑化 */
.el-drawer {
  background-color: #23252b !important;
  border-left: 1px solid #2e323b !important;
  box-shadow: -10px 0 30px rgba(0, 0, 0, 0.6) !important;
}

.el-drawer__header {
  border-bottom: 1px solid #2a2d36 !important;
  margin-bottom: 0 !important;
  padding: 18px 24px !important;
  color: #f0f6fc !important;
  font-size: 15px !important;
  font-weight: 600 !important;
}

.el-drawer__body {
  padding: 22px 24px !important;
}

/* 抽屉内单选组及各选项严格左对齐，去除默认居中与右侧外边距 */
.el-drawer .radio-vertical-stack {
  display: flex !important;
  flex-direction: column !important;
  align-items: flex-start !important;
  justify-content: flex-start !important;
  gap: 12px !important;
  width: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
}

.el-drawer .radio-vertical-stack .el-radio {
  display: flex !important;
  align-items: flex-start !important;
  justify-content: flex-start !important;
  width: 100% !important;
  height: auto !important;
  margin: 0 !important;
  padding: 4px 0 !important;
  white-space: normal !important;
}

.el-drawer .radio-vertical-stack .el-radio .el-radio__input {
  margin-top: 2px !important;
  flex-shrink: 0 !important;
}

.el-drawer .radio-vertical-stack .el-radio .el-radio__label {
  padding-left: 8px !important;
  display: flex !important;
  flex-direction: column !important;
  align-items: flex-start !important;
  text-align: left !important;
  white-space: normal !important;
  flex: 1 !important;
}

/* 表格深度定制 (消除图3图4表格割裂感) */
.el-table {
  background-color: transparent !important;
  --el-table-border-color: #2a2d36 !important;
  --el-table-header-bg-color: #282b33 !important;
  --el-table-row-hover-bg-color: #292c34 !important;
}

.el-table th.el-table__cell {
  background-color: #282b33 !important;
  color: #8b949e !important;
  font-weight: 600 !important;
  border-bottom: 1px solid #2a2d36 !important;
}

.el-table td.el-table__cell {
  background-color: #23252b !important;
  color: #cbd5e1 !important;
  border-bottom: 1px solid #2a2d36 !important;
}

.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background-color: #282b33 !important;
}

/* Tabs 标签页定制 */
.el-tabs__item {
  color: #8b949e !important;
  font-weight: 500 !important;
}

.el-tabs__item.is-active {
  color: #38bdf8 !important;
  font-weight: 600 !important;
}

.el-tabs__active-bar {
  background-color: #2563eb !important;
}

.el-tabs__nav-wrap::after {
  background-color: #2a2d36 !important;
}

/* 上传框定制 */
.el-upload-dragger {
  background-color: #1a1b1f !important;
  border: 1px dashed #2e323b !important;
  border-radius: 8px !important;
}

.el-upload-dragger:hover {
  border-color: #2563eb !important;
}

.el-upload__text {
  color: #8b949e !important;
}

.el-upload__text em {
  color: #38bdf8 !important;
}

/* 表单输入框暗黑定制 */
.el-input__wrapper {
  background-color: #1a1b1f !important;
  box-shadow: 0 0 0 1px #2e323b inset !important;
}

.el-input__wrapper.is-focus {
  box-shadow: 0 0 0 1px #2563eb inset !important;
}

.el-textarea__inner {
  background-color: #1a1b1f !important;
  color: #cbd5e1 !important;
  border: 1px solid #2e323b !important;
  border-radius: 6px !important;
}

.el-textarea__inner:focus {
  border-color: #2563eb !important;
}

/* ================= Docker 容器安全认证与初始化界面 ================= */
.auth-fullscreen-container {
  min-height: 100vh;
  width: 100vw;
  background-color: #0c0e12;
  background-image: 
    radial-gradient(circle at 50% 15%, rgba(37, 99, 235, 0.16), transparent 45%),
    radial-gradient(circle at 80% 80%, rgba(16, 185, 129, 0.05), transparent 35%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  box-sizing: border-box;
}

.auth-glass-card {
  width: 100%;
  max-width: 440px;
  background-color: rgba(22, 25, 32, 0.9);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 18px;
  padding: 38px 36px 32px 36px;
  box-shadow: 
    0 24px 60px rgba(0, 0, 0, 0.7),
    0 0 1px 1px rgba(255, 255, 255, 0.05);
  animation: authCardFadeIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes authCardFadeIn {
  from {
    opacity: 0;
    transform: translateY(14px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.auth-card-header {
  text-align: center;
  margin-bottom: 26px;
}

.auth-badge-docker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background-color: rgba(37, 99, 235, 0.12);
  border: 1px solid rgba(37, 99, 235, 0.3);
  color: #60a5fa;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
  margin-bottom: 14px;
}

.live-dot-blue {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #3b82f6;
  box-shadow: 0 0 8px #3b82f6;
}

.live-dot-green {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #10b981;
  box-shadow: 0 0 8px #10b981;
}

.auth-title {
  color: #f8fafc;
  font-size: 20px;
  font-weight: 700;
  margin: 0 0 8px 0;
  letter-spacing: -0.3px;
}

.auth-desc {
  color: #94a3b8;
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
}

.auth-form {
  margin-top: 20px;
}

.auth-form .el-form-item {
  margin-bottom: 18px;
}

.auth-form .el-form-item__label {
  color: #cbd5e1 !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  padding-bottom: 6px !important;
}

.auth-error-banner {
  background-color: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  font-size: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 16px;
  text-align: center;
}

.auth-submit-btn {
  width: 100%;
  height: 42px;
  background-color: #2563eb;
  border: none;
  border-radius: 8px;
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
  transition: all 0.15s ease;
  margin-top: 8px;
}

.auth-submit-btn:hover:not(:disabled) {
  background-color: #1d4ed8;
  box-shadow: 0 6px 18px rgba(37, 99, 235, 0.5);
}

.auth-submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

.auth-footer-tip {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  color: #64748b;
  font-size: 11px;
  line-height: 1.4;
  margin-top: 20px;
}

.tip-dot {
  color: #3b82f6;
  font-size: 14px;
  line-height: 1;
}

.danger-hover:hover {
  background-color: rgba(239, 68, 68, 0.15) !important;
  color: #ef4444 !important;
  border-color: rgba(239, 68, 68, 0.3) !important;
}

/* ================= 母本可视化与源码编辑器 (3X-UI 暗黑科技定制) ================= */
.xui-editor-dialog {
  border-radius: 14px !important;
  background-color: #17191e !important;
  border: 1px solid #2b303c !important;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7) !important;
}

.xui-editor-dialog .el-dialog__header {
  padding: 18px 28px 16px 28px !important;
  border-bottom: 1px solid #242832 !important;
  margin-right: 0 !important;
}

.xui-editor-dialog .el-dialog__title {
  color: #f1f5f9 !important;
  font-size: 16px !important;
  font-weight: 600 !important;
}

.xui-editor-dialog .el-dialog__body {
  padding: 22px 28px !important;
  background-color: #131519 !important;
}

.xui-editor-dialog .el-dialog__footer {
  padding: 16px 28px 18px 28px !important;
  border-top: 1px solid #242832 !important;
}

.editor-main-container {
  min-height: 580px;
  display: flex;
  flex-direction: column;
}

/* 顶部标签栏 */
.editor-tabs-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #242832;
}

.editor-segmented-tabs {
  display: inline-flex;
  background-color: #1a1d24;
  padding: 4px;
  border-radius: 8px;
  border: 1px solid #282d38;
  gap: 4px;
}

.editor-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 16px;
  border-radius: 6px;
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.editor-tab-btn:hover {
  color: #e2e8f0;
  background-color: rgba(255, 255, 255, 0.04);
}

.editor-tab-btn.active {
  background-color: #2563eb;
  color: #ffffff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.4);
}

.tab-count-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
  background-color: rgba(255, 255, 255, 0.15);
  color: inherit;
}

.editor-meta-pill-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.editor-meta-pill {
  display: inline-flex;
  align-items: center;
  background-color: #1e222a;
  border: 1px solid #2c323f;
  color: #94a3b8;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
}

/* 内容面板通用布局 */
.editor-tab-content-pane {
  display: flex;
  flex-direction: column;
}

.editor-toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  gap: 14px;
}

.editor-toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.editor-toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tb-count-text {
  font-size: 12px;
  color: #64748b;
}

.editor-empty-tip {
  grid-column: 1 / -1;
  text-align: center;
  color: #64748b;
  font-size: 13px;
  padding: 60px 20px;
}

/* 策略组 Zashboard 2列网格 */
.zashboard-groups-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  max-height: calc(82vh - 220px);
  overflow-y: auto;
  padding: 4px 10px 4px 4px;
}

.zashboard-groups-grid::-webkit-scrollbar,
.proxies-cards-grid::-webkit-scrollbar,
.z-card-chips-container::-webkit-scrollbar,
.add-nodes-scroll-area::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.zashboard-groups-grid::-webkit-scrollbar-track,
.proxies-cards-grid::-webkit-scrollbar-track,
.z-card-chips-container::-webkit-scrollbar-track,
.add-nodes-scroll-area::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.25);
  border-radius: 4px;
}

.zashboard-groups-grid::-webkit-scrollbar-thumb,
.proxies-cards-grid::-webkit-scrollbar-thumb,
.z-card-chips-container::-webkit-scrollbar-thumb,
.add-nodes-scroll-area::-webkit-scrollbar-thumb {
  background: #2c3240;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.04);
  transition: all 0.2s ease;
}

.zashboard-groups-grid::-webkit-scrollbar-thumb:hover,
.proxies-cards-grid::-webkit-scrollbar-thumb:hover,
.z-card-chips-container::-webkit-scrollbar-thumb:hover,
.add-nodes-scroll-area::-webkit-scrollbar-thumb:hover {
  background: #2563eb;
  box-shadow: 0 0 10px rgba(37, 99, 235, 0.6);
}

@media (max-width: 1080px) {
  .zashboard-groups-grid {
    grid-template-columns: 1fr;
  }
}

.z-group-card {
  background-color: #1a1d24;
  border: 1px solid #282d38;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  height: 310px;
  box-sizing: border-box;
  transition: all 0.2s ease;
  overflow: hidden;
}

.z-group-card:hover {
  border-color: #3b4252;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.z-card-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px 18px;
  background-color: #1e222b;
  border-bottom: 1px solid #282d38;
}

.z-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.z-group-name {
  font-size: 14px;
  font-weight: 600;
  color: #f1f5f9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 220px;
}

.z-type-pill {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.z-type-pill.type-select {
  background-color: rgba(37, 99, 235, 0.2);
  color: #60a5fa;
  border: 1px solid rgba(37, 99, 235, 0.4);
}

.z-type-pill.type-url-test {
  background-color: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.4);
}

.z-type-pill.type-fallback {
  background-color: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.4);
}

.z-type-pill.type-load-balance {
  background-color: rgba(168, 85, 247, 0.2);
  color: #c084fc;
  border: 1px solid rgba(168, 85, 247, 0.4);
}

.z-node-count-badge {
  font-size: 11px;
  color: #94a3b8;
  background-color: rgba(255, 255, 255, 0.05);
  padding: 2px 7px;
  border-radius: 4px;
  white-space: nowrap;
}

.z-header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.z-action-btn {
  background-color: #262b36;
  border: 1px solid #363c4a;
  color: #cbd5e1;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s ease;
}

.z-action-btn:hover {
  background-color: #323846;
  color: #ffffff;
  border-color: #4a5264;
}

.z-action-btn.primary {
  background-color: rgba(37, 99, 235, 0.15);
  border-color: rgba(37, 99, 235, 0.35);
  color: #60a5fa;
}

.z-action-btn.primary:hover {
  background-color: #2563eb;
  color: #ffffff;
}

.z-action-btn.danger {
  color: #94a3b8;
}

.z-action-btn.danger:hover {
  background-color: rgba(239, 68, 68, 0.2);
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.4);
}

.z-card-submeta {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 6px 18px;
  background-color: rgba(0, 0, 0, 0.18);
  border-bottom: 1px solid #232731;
  font-size: 11px;
  color: #64748b;
}

.z-meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}

.z-card-chips-container {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px 14px 14px 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-content: flex-start;
  box-sizing: border-box;
}

.z-card-chips-container::-webkit-scrollbar {
  width: 6px;
}

.z-card-chips-container::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 3px;
}

.z-card-chips-container::-webkit-scrollbar-thumb {
  background: #363d4d;
  border-radius: 3px;
}

.z-card-chips-container::-webkit-scrollbar-thumb:hover {
  background: #4b5568;
}

.z-node-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background-color: #232731;
  border: 1px solid #333845;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  color: #e2e8f0;
  cursor: grab;
  user-select: none;
  transition: all 0.15s ease;
}

.z-node-chip:hover {
  background-color: #2c3240;
  border-color: #475166;
}

.z-node-chip:active {
  cursor: grabbing;
}

.z-node-chip.is-dragging {
  opacity: 0.35;
  border-style: dashed;
  border-color: #3b82f6;
}

.z-node-chip.is-drop-target {
  border-color: #3b82f6 !important;
  background-color: rgba(59, 130, 246, 0.15) !important;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
}

.z-drag-handle {
  color: #64748b;
  font-size: 11px;
  line-height: 1;
}

.z-node-chip:hover .z-drag-handle {
  color: #94a3b8;
}

.z-proto-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.z-proto-tag.proto-vless {
  background-color: rgba(168, 85, 247, 0.2);
  color: #c084fc;
}

.z-proto-tag.proto-hysteria2 {
  background-color: rgba(6, 182, 212, 0.2);
  color: #22d3ee;
}

.z-proto-tag.proto-vmess {
  background-color: rgba(37, 99, 235, 0.2);
  color: #60a5fa;
}

.z-proto-tag.proto-ss {
  background-color: rgba(16, 185, 129, 0.2);
  color: #34d399;
}

.z-proto-tag.proto-trojan {
  background-color: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}

.z-proto-tag.proto-direct {
  background-color: rgba(59, 130, 246, 0.2);
  color: #93c5fd;
}

.z-proto-tag.proto-reject {
  background-color: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.z-proto-tag.proto-group {
  background-color: rgba(236, 72, 153, 0.2);
  color: #f472b6;
}

.z-proto-tag.proto-node, .z-proto-tag.proto-custom, .z-proto-tag.proto-proxy {
  background-color: rgba(148, 163, 184, 0.2);
  color: #cbd5e1;
}

.z-chip-name {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.z-chip-del-btn {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  font-size: 13px;
  padding: 0 2px;
  line-height: 1;
  border-radius: 2px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.z-chip-del-btn:hover {
  color: #ef4444;
  background-color: rgba(239, 68, 68, 0.2);
}

.z-add-chip-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background-color: transparent;
  border: 1px dashed #3a4150;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s ease;
}

.z-add-chip-btn:hover {
  border-color: #3b82f6;
  color: #60a5fa;
  background-color: rgba(59, 130, 246, 0.08);
}

.z-empty-group-tip {
  width: 100%;
  text-align: center;
  color: #64748b;
  font-size: 12px;
  padding: 24px 10px;
}

/* 节点卡片列表网格 */
.proxies-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  max-height: calc(82vh - 220px);
  overflow-y: auto;
  padding: 4px;
}

.editor-node-card {
  background-color: #1a1d24;
  border: 1px solid #282d38;
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: all 0.2s ease;
}

.editor-node-card:hover {
  border-color: #3b4252;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
}

.n-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.n-card-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.n-icon-btn {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.n-icon-btn.edit:hover {
  color: #60a5fa;
  background-color: rgba(96, 165, 250, 0.15);
}

.n-icon-btn.delete:hover {
  color: #ef4444;
  background-color: rgba(239, 68, 68, 0.15);
}

.n-card-title {
  font-size: 14px;
  font-weight: 600;
  color: #f1f5f9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.n-card-server {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #94a3b8;
  font-family: Consolas, Monaco, monospace;
}
.n-card-location {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.n-card-location .loc-icon {
  font-size: 13px;
  color: #38bdf8;
  flex-shrink: 0;
}

.n-card-location .loc-flag {
  font-size: 14px;
  line-height: 1;
  flex-shrink: 0;
}

.n-card-location .loc-text {
  font-size: 12px;
  font-weight: 500;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}


.country-flag-svg {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 12px;
  border-radius: 2px;
  overflow: hidden;
  box-shadow: 0 0 1px rgba(0, 0, 0, 0.4);
  flex-shrink: 0;
  vertical-align: middle;
}

.country-flag-svg svg {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.node-loc-flag-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 1px 3px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.07);
  line-height: 1;
  flex-shrink: 0;
  cursor: default;
}

.xui-node-card.card-selected .node-loc-flag-badge {
  background: rgba(96, 165, 250, 0.15);
  border-color: rgba(96, 165, 250, 0.3);
}
.node-proto-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
}

.node-loc-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: #94a3b8;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.06);
  padding: 1px 6px;
  border-radius: 4px;
  white-space: nowrap;
  font-weight: 500;
}

.xui-node-card.card-selected .node-loc-badge {
  background: rgba(96, 165, 250, 0.15);
  border-color: rgba(96, 165, 250, 0.3);
  color: #93c5fd;
}


.server-icon {
  font-size: 13px;
  color: #64748b;
}

.server-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.n-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 2px;
  padding-top: 8px;
  border-top: 1px solid #232731;
}

.n-card-footer .node-delay-pill {
  margin-left: auto;
}

.groups-included-pill {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  color: #64748b;
  background-color: rgba(255, 255, 255, 0.04);
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #282d38;
}

.node-protocol-tag {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
}

.node-protocol-tag.proto-hysteria2 {
  background-color: rgba(6, 182, 212, 0.2);
  color: #22d3ee;
  border: 1px solid rgba(6, 182, 212, 0.3);
}

.node-protocol-tag.proto-vless {
  background-color: rgba(168, 85, 247, 0.2);
  color: #c084fc;
  border: 1px solid rgba(168, 85, 247, 0.3);
}

.node-protocol-tag.proto-vmess {
  background-color: rgba(37, 99, 235, 0.2);
  color: #60a5fa;
  border: 1px solid rgba(37, 99, 235, 0.3);
}

.node-protocol-tag.proto-ss {
  background-color: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.node-protocol-tag.proto-trojan {
  background-color: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

/* YAML 源码面板 */
.editor-yaml-layout {
  display: flex;
  flex-direction: column;
  height: 520px;
}

.yaml-toolbar-tip {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 12px;
}

/* 底部操作条 */
.editor-footer-flex {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.footer-callout .f-tip {
  font-size: 12px;
  color: #64748b;
}

/* 添加节点弹窗布局 */
.add-nodes-modal-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.add-nodes-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.quick-pick-btns {
  display: flex;
  align-items: center;
  gap: 6px;
}

.btn-xs {
  height: 26px !important;
  font-size: 11px !important;
  padding: 0 8px !important;
}

.add-nodes-scroll-area {
  max-height: 420px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-right: 4px;
}

.node-category-section {
  background-color: #17191e;
  border: 1px solid #262a34;
  border-radius: 8px;
  padding: 10px 14px;
}

.cat-title {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  margin-bottom: 8px;
}

.cat-checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 6px;
}

.node-select-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 6px;
  background-color: #1f232b;
  border: 1px solid #2a2e38;
  font-size: 12px;
  color: #cbd5e1;
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

.node-select-item:hover:not(.already-in) {
  background-color: #262c37;
  border-color: #3b4455;
}

.node-select-item.selected {
  background-color: rgba(37, 99, 235, 0.15);
  border-color: #2563eb;
  color: #93c5fd;
}

.node-select-item.already-in {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: rgba(0, 0, 0, 0.2);
}

.select-item-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.already-badge {
  font-size: 10px;
  color: #64748b;
  margin-left: auto;
}

.btn-sm {
  height: 28px !important;
  font-size: 12px !important;
  padding: 0 10px !important;
}

/* ================= 移动端 / 手机端 UI 适配规范 (Global Dialogs & Editor) ================= */
@media (max-width: 768px) {
  /* 全局弹窗宽度自适应全屏微留白 */
  .el-dialog,
  .xui-custom-dialog,
  .xui-editor-dialog,
  .fetch-progress-dialog,
  .remote-upload-dialog {
    width: 95vw !important;
    max-width: 95vw !important;
    margin: 10px auto !important;
    border-radius: 12px !important;
  }

  .el-dialog__header {
    padding: 12px 16px !important;
  }

  .el-dialog__title {
    font-size: 15px !important;
  }

  .el-dialog__body {
    padding: 14px 14px !important;
    max-height: 75vh !important;
    overflow-y: auto !important;
  }

  .el-dialog__footer {
    padding: 10px 16px !important;
  }

  /* 弹窗抽屉全屏适配 */
  .el-drawer,
  .xui-custom-drawer {
    width: 100% !important;
    max-width: 100vw !important;
  }

  /* 表单多列在手机端自动转单列 */
  .form-cols-2,
  .form-cols-3 {
    display: flex !important;
    flex-direction: column !important;
    gap: 6px !important;
  }

  .el-form-item {
    margin-bottom: 12px !important;
  }

  /* 母本可视化编辑器弹窗移动端适配 */
  .editor-tabs-bar {
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 8px !important;
    margin-bottom: 12px !important;
    padding-bottom: 10px !important;
  }

  .editor-segmented-tabs {
    display: flex !important;
    width: 100% !important;
    box-sizing: border-box !important;
  }

  .editor-tab-btn {
    flex: 1 !important;
    justify-content: center !important;
    padding: 6px 4px !important;
    font-size: 11px !important;
    gap: 4px !important;
  }

  .tab-count-badge {
    font-size: 10px !important;
    padding: 1px 4px !important;
  }

  .editor-meta-pill-group {
    display: none !important;
  }

  .editor-toolbar-row {
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 8px !important;
    margin-bottom: 10px !important;
  }

  .editor-toolbar-left {
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 6px !important;
  }

  .editor-toolbar-left .el-input {
    width: 100% !important;
  }

  .editor-toolbar-right {
    width: 100% !important;
  }

  .editor-toolbar-right button {
    width: 100% !important;
    justify-content: center !important;
  }

  /* 策略组 Zashboard 手机端单列铺满 */
  .zashboard-groups-grid {
    grid-template-columns: 1fr !important;
    gap: 12px !important;
    max-height: calc(85vh - 200px) !important;
    padding-right: 2px !important;
  }

  .z-group-card {
    height: auto !important;
    min-height: 220px !important;
    max-height: 380px !important;
  }

  .z-card-header {
    padding: 10px 12px !important;
    flex-wrap: wrap !important;
    gap: 6px !important;
  }

  .z-header-left {
    flex: 1 1 100% !important;
    gap: 6px !important;
    justify-content: space-between !important;
  }

  .z-group-name {
    max-width: 140px !important;
    font-size: 13px !important;
  }

  .z-header-actions {
    width: 100% !important;
    justify-content: flex-end !important;
    gap: 6px !important;
    margin-top: 4px !important;
  }

  .z-action-btn {
    padding: 4px 6px !important;
    font-size: 11px !important;
  }

  .z-card-submeta {
    padding: 5px 12px !important;
    font-size: 10px !important;
    gap: 8px !important;
    flex-wrap: wrap !important;
  }

  .z-card-chips-container {
    padding: 8px 10px !important;
    gap: 6px !important;
    max-height: 250px !important;
  }

  .z-node-chip {
    padding: 3px 6px !important;
    font-size: 11px !important;
    max-width: 100% !important;
  }

  .z-chip-name {
    max-width: 110px !important;
  }

  /* 节点列表网格手机端单列 */
  .proxies-cards-grid {
    grid-template-columns: 1fr !important;
    gap: 10px !important;
    max-height: calc(85vh - 200px) !important;
  }

  .editor-node-card {
    padding: 12px 12px !important;
  }

  .editor-footer-flex {
    flex-direction: column !important;
    gap: 8px !important;
    align-items: stretch !important;
  }

  .footer-callout {
    font-size: 11px !important;
    text-align: center !important;
  }

  .editor-footer-flex .footer-btns {
    display: flex !important;
    gap: 8px !important;
    width: 100% !important;
  }

  .editor-footer-flex .footer-btns button {
    flex: 1 !important;
    justify-content: center !important;
    margin-left: 0 !important;
  }

  /* 添加节点弹窗手机端 */
  .add-nodes-toolbar {
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 6px !important;
  }

  .add-nodes-toolbar .el-input {
    width: 100% !important;
  }

  .quick-pick-btns {
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 4px !important;
  }

  .quick-pick-btns button {
    flex: 1 !important;
    text-align: center !important;
  }

  .cat-checkbox-grid {
    grid-template-columns: 1fr !important;
    gap: 4px !important;
  }

  .add-nodes-scroll-area {
    max-height: 52vh !important;
  }

  /* 登录与初始化页面手机端 */
  .auth-fullscreen-container {
    padding: 14px 10px !important;
  }

  .auth-glass-card {
    padding: 24px 16px !important;
    border-radius: 14px !important;
  }

  .auth-title {
    font-size: 18px !important;
  }

  .auth-desc {
    font-size: 12px !important;
  }

  .auth-submit-btn {
    height: 44px !important;
    font-size: 13px !important;
  }

  /* 表格在移动端优化 */
  .xui-custom-table {
    font-size: 12px !important;
  }

  .upload-3x-panel .el-upload-dragger {
    padding: 20px 10px !important;
  }
}
</style>
