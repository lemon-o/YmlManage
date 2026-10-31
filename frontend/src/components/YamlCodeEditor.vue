<template>
  <div class="vscode-editor-window" :class="{ 'is-fullscreen': isFullscreen }" :style="isFullscreen ? {} : { height: height || '560px' }">
    <!-- 1. VS Code 风格顶部标签栏 (Tab Header) -->
    <div class="vscode-tabs-header">
      <div class="vscode-tabs-container">
        <!-- 激活的 YAML 文件标签 -->
        <div class="vscode-tab active" :title="profileName || '优选节点.yml'">
          <!-- VS Code YAML 标志图标 -->
          <span class="tab-icon-yaml">YML</span>
          <span class="tab-title">{{ profileName || '优选节点.yml' }}</span>
          <span v-if="isContentDirty" class="tab-dirty-indicator" title="内容已编辑">●</span>
        </div>
      </div>

      <!-- 右侧 VS Code 扁平风格操作栏 -->
      <div class="vscode-actions-toolbar">
        <!-- Tab 制表符检测修复 (YAML 语法纠错) -->
        <button
          v-if="hasTabChars"
          type="button"
          class="vsc-action-btn warn-action"
          title="检测到文件中含有 Tab 制表符（YAML 语法严禁使用 Tab），点击一键转为 2 个标准空格"
          @click="fixTabsToSpaces"
        >
          <el-icon><MagicStick /></el-icon>
          <span>修复 Tab (转2空格)</span>
        </button>

        <!-- 查找与替换 (Ctrl+F) -->
        <button
          type="button"
          class="vsc-action-btn"
          title="在代码中查找与替换 (快捷键 Ctrl+F)"
          @click="openSearchWidget"
        >
          <el-icon><Search /></el-icon>
          <span>查找</span>
        </button>

        <!-- 自动换行切换 -->
        <button
          type="button"
          class="vsc-action-btn"
          :class="{ active: isWrapLines }"
          :title="isWrapLines ? '切换为不自动换行 (水平横向滚动)' : '切换为自动换行 (Soft Wrap)'"
          @click="toggleWrapLines"
        >
          <el-icon><Operation /></el-icon>
          <span>{{ isWrapLines ? '换行: 开' : '换行: 关' }}</span>
        </button>

        <!-- 一键复制 -->
        <button
          type="button"
          class="vsc-action-btn"
          title="复制当前全部 YAML 源码至剪贴板"
          @click="handleCopyCode"
        >
          <el-icon><DocumentCopy /></el-icon>
          <span>复制</span>
        </button>

        <!-- 全屏 / 还原 -->
        <button
          type="button"
          class="vsc-action-btn"
          :title="isFullscreen ? '退出全屏 (Esc)' : '全屏沉浸编辑'"
          @click="toggleFullscreen"
        >
          <el-icon>
            <FullScreen v-if="!isFullscreen" />
            <Aim v-else />
          </el-icon>
          <span>{{ isFullscreen ? '还原' : '全屏' }}</span>
        </button>
      </div>
    </div>

    <!-- 2. VS Code 风格面包屑导航栏 (Breadcrumbs) -->
    <div class="vscode-breadcrumbs-bar">
      <span class="crumb-text">母本文件</span>
      <span class="crumb-chevron">›</span>
      <span class="crumb-text">{{ profileName || '优选节点.yml' }}</span>
      <span class="crumb-chevron">›</span>
      <span class="crumb-text highlight">YAML 源码</span>
    </div>

    <!-- 3. VS Code 经典 Dark+ 核心编辑区域 -->
    <div class="vscode-editor-body" ref="containerRef">
      <codemirror
        v-model="internalValue"
        :placeholder="placeholder"
        :style="{ height: '100%' }"
        :autofocus="false"
        :indent-with-tab="false"
        :tab-size="2"
        :phrases="chinesePhrases"
        :extensions="editorExtensions"
        @change="handleCodeChange"
        @ready="handleEditorReady"
      />
    </div>

    <!-- 4. VS Code 经典蓝色状态栏 (Status Bar) -->
    <div class="vscode-status-bar">
      <div class="status-section-left">
        <span class="status-item branch-pill">
          <el-icon :size="11" style="margin-right: 3px;"><Check /></el-icon>
          <span>就绪</span>
        </span>
        <span class="status-item">行 {{ cursorInfo.line }}, 列 {{ cursorInfo.col }}</span>
        <span class="status-item">空格: 2</span>
        <span class="status-item">UTF-8</span>
        <span class="status-item">CRLF</span>
      </div>

      <div class="status-section-right">
        <span class="status-item stats-count">{{ lineCount }} 行, {{ charCount }} 字符</span>
        <span class="status-item lang-selector" title="语言模式: YAML">YAML</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, shallowRef, onBeforeUnmount } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { yaml } from '@codemirror/lang-yaml'
import { vscodeDark } from '@uiw/codemirror-theme-vscode'
import { EditorView, keymap, lineNumbers, highlightActiveLineGutter, highlightActiveLine } from '@codemirror/view'
import { EditorState, Compartment } from '@codemirror/state'
import { defaultKeymap, indentWithTab, history, historyKeymap } from '@codemirror/commands'
import { search, searchKeymap, highlightSelectionMatches, openSearchPanel, closeSearchPanel } from '@codemirror/search'
import { bracketMatching, foldGutter, foldKeymap, indentUnit } from '@codemirror/language'
import { ElMessage } from 'element-plus'
import {
  Operation,
  DocumentCopy,
  FullScreen,
  Aim,
  MagicStick,
  Check,
  Search
} from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  profileName: {
    type: String,
    default: '优选节点.yml'
  },
  height: {
    type: String,
    default: '540px'
  },
  placeholder: {
    type: String,
    default: '正在加载或编辑 YAML 源码...'
  },
  readonly: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

// 内部双向绑定值
const internalValue = ref(props.modelValue || '')
const initialLoadedValue = ref(props.modelValue || '')

watch(() => props.modelValue, (newVal) => {
  if (newVal !== internalValue.value) {
    internalValue.value = newVal || ''
    if (!initialLoadedValue.value && newVal) {
      initialLoadedValue.value = newVal
    }
  }
})

// 内容是否已编辑变动
const isContentDirty = computed(() => {
  return initialLoadedValue.value && internalValue.value !== initialLoadedValue.value
})

// 光标位置
const cursorInfo = ref({ line: 1, col: 1 })

// 软换行状态与全屏状态
const isWrapLines = ref(true)
const isFullscreen = ref(false)

// CodeMirror View 实例
const viewRef = shallowRef(null)

// 动态扩展配置隔离器
const wrapCompartment = new Compartment()
const readonlyCompartment = new Compartment()

// VS Code 深度定制微调主题
const vscodeCustomOverrides = EditorView.theme({
  '&': {
    backgroundColor: '#1e1e1e !important',
    color: '#d4d4d4 !important',
    fontFamily: 'Consolas, Monaco, "Courier New", monospace !important',
    fontSize: '13px !important'
  },
  '.cm-content': {
    caretColor: '#aeafad !important',
    padding: '6px 0 !important',
    fontFamily: 'Consolas, Monaco, "Courier New", monospace !important'
  },
  '&.cm-focused .cm-cursor': {
    borderLeftColor: '#aeafad !important',
    borderLeftWidth: '2px !important'
  },
  '&.cm-focused .cm-selectionBackground, ::selection': {
    backgroundColor: '#264f78 !important'
  },
  '.cm-gutters': {
    backgroundColor: '#1e1e1e !important',
    color: '#858585 !important',
    borderRight: '1px solid #282828 !important',
    paddingRight: '6px !important'
  },
  '.cm-activeLineGutter': {
    backgroundColor: '#282828 !important',
    color: '#c6c6c6 !important'
  },
  '.cm-activeLine': {
    backgroundColor: 'rgba(255, 255, 255, 0.035) !important'
  },
  '.cm-foldGutter': {
    width: '18px !important'
  },
  '.cm-foldGutter span': {
    display: 'inline-flex !important',
    alignItems: 'center !important',
    justifyContent: 'center !important',
    width: '16px !important',
    height: '16px !important',
    color: '#858585 !important',
    cursor: 'pointer !important',
    fontSize: '11px !important',
    lineHeight: '1 !important',
    transition: 'color 0.15s ease'
  },
  '.cm-foldGutter span:hover': {
    color: '#ffffff !important'
  },
  '.cm-foldPlaceholder': {
    backgroundColor: '#2a2d2e !important',
    border: '1px solid #3c3c3c !important',
    color: '#8c8c8c !important',
    borderRadius: '3px !important',
    padding: '0 6px !important',
    margin: '0 4px !important',
    fontFamily: 'inherit'
  },
  '.cm-scroller': {
    height: '100% !important',
    maxHeight: '100% !important',
    overflowY: 'scroll !important',
    overflowX: 'auto !important',
    fontFamily: 'Consolas, Monaco, "Courier New", monospace !important'
  },
  '.cm-scroller::-webkit-scrollbar': {
    width: '12px !important',
    height: '12px !important',
    display: 'block !important'
  },
  '.cm-scroller::-webkit-scrollbar-track': {
    background: '#1e1e1e !important'
  },
  '.cm-scroller::-webkit-scrollbar-thumb': {
    background: 'rgba(121, 121, 121, 0.55) !important',
    borderRadius: '6px !important',
    border: '2px solid #1e1e1e !important'
  },
  '.cm-scroller::-webkit-scrollbar-thumb:hover': {
    background: 'rgba(160, 160, 160, 0.85) !important'
  },
  '.cm-scroller::-webkit-scrollbar-thumb:active': {
    background: '#007acc !important'
  },
  '.cm-scroller::-webkit-scrollbar-corner': {
    background: '#1e1e1e !important'
  }
}, { dark: true })

// 监听光标移动扩展
const cursorListener = EditorView.updateListener.of((update) => {
  if (update.selectionSet || update.docChanged) {
    const pos = update.state.selection.main.head
    const line = update.state.doc.lineAt(pos)
    cursorInfo.value = {
      line: line.number,
      col: pos - line.from + 1
    }
  }
})

// Tab 键智能转为 2 个标准空格（严格遵循 YAML 规范）
const customIndentKeymap = keymap.of([
  {
    key: 'Tab',
    run: (view) => {
      view.dispatch(view.state.replaceSelection('  '))
      return true
    }
  }
])

// CodeMirror 国际化中文语言包 (查找、替换、代码折叠等组件汉化)
const chinesePhrases = {
  // 查找与替换面板
  'Find': '查找',
  'Replace': '替换',
  'next': '下一个',
  'previous': '上一个',
  'all': '全部',
  'match case': '区分大小写',
  'regexp': '正则表达式',
  'by word': '全字匹配',
  'replace': '替换',
  'replace all': '全部替换',
  'close': '关闭',
  'current match': '当前匹配项',
  'on line': '在第几行',
  'replaced match on line $': '已替换第 $ 行的匹配项',
  'replaced $ matches': '已替换 $ 处匹配项',
  'Go to line': '跳转到行',
  'go': '前往',
  // 代码折叠
  'Fold line': '折叠代码块',
  'Unfold line': '展开代码块',
  'Folded lines': '已折叠代码行',
  'Unfolded lines': '已展开代码行',
  'folded code': '已折叠代码',
  'unfold': '展开'
}

// 组合扩展列表：包含原汁原味的 VS Code Dark+ 主题
const editorExtensions = computed(() => {
  return [
    lineNumbers(),
    highlightActiveLineGutter(),
    highlightActiveLine(),
    history(),
    foldGutter({
      openText: '⌄',
      closedText: '›'
    }),
    bracketMatching(),
    highlightSelectionMatches(),
    EditorState.phrases.of(chinesePhrases),
    search({ top: true }),
    indentUnit.of('  '),
    yaml(),
    vscodeDark,
    vscodeCustomOverrides,
    cursorListener,
    wrapCompartment.of(isWrapLines.value ? EditorView.lineWrapping : []),
    readonlyCompartment.of(EditorState.readOnly.of(props.readonly)),
    customIndentKeymap,
    keymap.of([
      ...defaultKeymap,
      ...searchKeymap,
      ...historyKeymap,
      ...foldKeymap
    ])
  ]
})

// 编辑器就绪回调
const handleEditorReady = (payload) => {
  viewRef.value = payload.view
}

// 代码变更事件
const handleCodeChange = (val) => {
  emit('update:modelValue', val)
  emit('change', val)
}

// 统计信息
const lineCount = computed(() => {
  if (!internalValue.value) return 1
  return internalValue.value.split('\n').length
})

const charCount = computed(() => {
  return (internalValue.value || '').length
})

// 检测是否误混入 Tab 制表符
const hasTabChars = computed(() => {
  return (internalValue.value || '').includes('\t')
})

// 一键将所有 Tab 制表符转为 2 空格
const fixTabsToSpaces = () => {
  if (!internalValue.value) return
  const fixed = internalValue.value.replace(/\t/g, '  ')
  internalValue.value = fixed
  emit('update:modelValue', fixed)
  emit('change', fixed)
  ElMessage.success('已成功将所有 Tab 制表符转换为 2 个标准空格')
}

// 打开查找与替换悬浮面板
const openSearchWidget = () => {
  if (viewRef.value) {
    openSearchPanel(viewRef.value)
  }
}

// 切换自动换行
const toggleWrapLines = () => {
  isWrapLines.value = !isWrapLines.value
  if (viewRef.value) {
    viewRef.value.dispatch({
      effects: wrapCompartment.reconfigure(isWrapLines.value ? EditorView.lineWrapping : [])
    })
  }
}

// 复制全部源码
const handleCopyCode = async () => {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(internalValue.value || '')
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = internalValue.value || ''
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    ElMessage.success('YAML 源码已复制至剪贴板')
  } catch (err) {
    ElMessage.error('复制失败，请手动选中文本复制')
  }
}

// 全屏切换
const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
}

// 快捷键 ESC 退出全屏
const handleKeyDown = (e) => {
  if (e.key === 'Escape' && isFullscreen.value) {
    isFullscreen.value = false
  }
}

window.addEventListener('keydown', handleKeyDown)
onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<style scoped>
/* VS Code 窗口框架容器 */
.vscode-editor-window {
  display: flex;
  flex-direction: column;
  background-color: #1e1e1e;
  border: 1px solid #2d2d2d;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.45);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

/* 全屏沉浸模式 */
.vscode-editor-window.is-fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100vw;
  height: 100vh;
  z-index: 3500;
  border-radius: 0;
  border: none;
}

/* 1. 顶部 Tab 标签栏 (VS Code editorGroupHeader.tabsBackground: #252526) */
.vscode-tabs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #252526;
  border-bottom: 1px solid #1e1e1e;
  height: 35px;
  user-select: none;
}

.vscode-tabs-container {
  display: flex;
  align-items: stretch;
  height: 100%;
}

.vscode-tab {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 14px;
  font-size: 12px;
  color: #969696;
  background-color: #2d2d2d;
  border-right: 1px solid #252526;
  border-top: 1px solid transparent;
  cursor: pointer;
  position: relative;
  transition: all 0.15s ease;
}

.vscode-tab.active {
  background-color: #1e1e1e;
  color: #ffffff;
  border-top: 1px solid #007acc;
  font-weight: 500;
}

.tab-icon-yaml {
  font-size: 9px;
  font-weight: 800;
  color: #e5c07b;
  background: rgba(229, 192, 123, 0.15);
  border: 1px solid rgba(229, 192, 123, 0.3);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: Consolas, monospace;
}

.tab-title {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tab-dirty-indicator {
  font-size: 10px;
  color: #ffffff;
  margin-left: 2px;
  opacity: 0.8;
}

/* 右侧 VS Code 扁平按钮组 */
.vscode-actions-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-right: 10px;
}

.vsc-action-btn {
  background: transparent;
  border: 1px solid transparent;
  color: #cccccc;
  border-radius: 4px;
  font-size: 11px;
  padding: 3px 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.vsc-action-btn:hover {
  background: #37373d;
  color: #ffffff;
}

.vsc-action-btn.active {
  background: #094771;
  color: #ffffff;
}

.vsc-action-btn.warn-action {
  color: #cca700;
  border-color: rgba(204, 167, 0, 0.35);
  background: rgba(204, 167, 0, 0.1);
}

.vsc-action-btn.warn-action:hover {
  background: rgba(204, 167, 0, 0.2);
}

/* 2. 面包屑导航栏 (Breadcrumb) */
.vscode-breadcrumbs-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  background-color: #1e1e1e;
  border-bottom: 1px solid #282828;
  padding: 4px 14px;
  font-size: 11px;
  color: #8c8c8c;
  user-select: none;
}

.crumb-text {
  color: #8c8c8c;
}

.crumb-text.highlight {
  color: #cccccc;
  font-weight: 500;
}

.crumb-chevron {
  color: #6e6e6e;
  font-size: 12px;
}

/* 3. 编辑器核心内容区 (不全屏时严格自适应高并展示右侧纵向滚动条) */
.vscode-editor-body {
  position: relative;
  flex: 1 1 0;
  min-height: 0;
  height: 100%;
  width: 100%;
  overflow: hidden;
  background-color: #1e1e1e;
}

.vscode-editor-body :deep(.cm-editor) {
  position: relative;
  height: 100% !important;
  max-height: 100% !important;
  outline: none !important;
}

.vscode-editor-body :deep(.cm-scroller) {
  height: 100% !important;
  max-height: 100% !important;
  line-height: 1.55;
  overflow-y: scroll !important;
  overflow-x: auto !important;
  scrollbar-width: thin;
  scrollbar-color: rgba(136, 136, 136, 0.55) #1e1e1e;
}

/* VS Code 经典滚动条 (支持 WebKit 与标准滚动条样式) */
.vscode-editor-body :deep(.cm-scroller::-webkit-scrollbar),
.vscode-editor-body :deep(::-webkit-scrollbar) {
  width: 12px !important;
  height: 12px !important;
  display: block !important;
}

.vscode-editor-body :deep(.cm-scroller::-webkit-scrollbar-track),
.vscode-editor-body :deep(::-webkit-scrollbar-track) {
  background: #1e1e1e !important;
}

.vscode-editor-body :deep(.cm-scroller::-webkit-scrollbar-thumb),
.vscode-editor-body :deep(::-webkit-scrollbar-thumb) {
  background: rgba(121, 121, 121, 0.55) !important;
  border-radius: 6px !important;
  border: 2px solid #1e1e1e !important;
}

.vscode-editor-body :deep(.cm-scroller::-webkit-scrollbar-thumb:hover),
.vscode-editor-body :deep(::-webkit-scrollbar-thumb:hover) {
  background: rgba(160, 160, 160, 0.85) !important;
}

.vscode-editor-body :deep(.cm-scroller::-webkit-scrollbar-thumb:active),
.vscode-editor-body :deep(::-webkit-scrollbar-thumb:active) {
  background: #007acc !important;
}

/* ========================================================
   VS Code 风格右上角悬浮查找/替换框 (Find Widget)
   ======================================================== */
.vscode-editor-body :deep(.cm-panels.cm-panels-top) {
  position: absolute !important;
  top: 10px !important;
  right: 20px !important;
  z-index: 200 !important;
  background: transparent !important;
  border: none !important;
  pointer-events: none !important;
}

.vscode-editor-body :deep(.cm-panels.cm-panels-bottom) {
  display: none !important;
}

.vscode-editor-body :deep(.cm-panel.cm-search) {
  pointer-events: auto !important;
  position: relative !important;
  background: #252526 !important;
  border: 1px solid #454545 !important;
  border-radius: 4px !important;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.65) !important;
  padding: 8px 32px 8px 12px !important;
  color: #cccccc !important;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
  font-size: 12px !important;
  line-height: 1.4 !important;
  display: block !important;
}

.vscode-editor-body :deep(.cm-panel.cm-search input.cm-textfield) {
  background-color: #3c3c3c !important;
  border: 1px solid #3c3c3c !important;
  color: #cccccc !important;
  border-radius: 2px !important;
  padding: 3px 8px !important;
  font-size: 12px !important;
  font-family: Consolas, Monaco, monospace !important;
  outline: none !important;
  width: 170px !important;
  height: 25px !important;
  box-sizing: border-box !important;
  vertical-align: middle !important;
  transition: border-color 0.15s ease !important;
  margin: 3px 6px 3px 0 !important;
}

.vscode-editor-body :deep(.cm-panel.cm-search input.cm-textfield:focus) {
  border-color: #007acc !important;
  box-shadow: 0 0 0 1px #007acc !important;
}

.vscode-editor-body :deep(.cm-panel.cm-search input.cm-textfield::placeholder) {
  color: #8c8c8c !important;
}

.vscode-editor-body :deep(.cm-panel.cm-search button.cm-button) {
  background-color: #333333 !important;
  border: 1px solid #454545 !important;
  color: #cccccc !important;
  border-radius: 2px !important;
  padding: 0 9px !important;
  height: 25px !important;
  font-size: 11px !important;
  cursor: pointer !important;
  margin: 3px 3px !important;
  vertical-align: middle !important;
  transition: all 0.15s ease !important;
  box-sizing: border-box !important;
}

.vscode-editor-body :deep(.cm-panel.cm-search button.cm-button:hover) {
  background-color: #444444 !important;
  color: #ffffff !important;
  border-color: #555555 !important;
}

.vscode-editor-body :deep(.cm-panel.cm-search button.cm-button:active) {
  background-color: #0e639c !important;
  border-color: #007acc !important;
}

.vscode-editor-body :deep(.cm-panel.cm-search label) {
  color: #9d9d9d !important;
  font-size: 11px !important;
  display: inline-flex !important;
  align-items: center !important;
  margin: 0 6px 0 2px !important;
  cursor: pointer !important;
  user-select: none !important;
  vertical-align: middle !important;
}

.vscode-editor-body :deep(.cm-panel.cm-search label:hover) {
  color: #ffffff !important;
}

.vscode-editor-body :deep(.cm-panel.cm-search input[type="checkbox"]) {
  accent-color: #007acc !important;
  margin-right: 4px !important;
  cursor: pointer !important;
  vertical-align: middle !important;
}

.vscode-editor-body :deep(.cm-panel.cm-search button[name="close"]) {
  position: absolute !important;
  top: 6px !important;
  right: 6px !important;
  width: 20px !important;
  height: 20px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  background: transparent !important;
  border: none !important;
  color: #858585 !important;
  font-size: 16px !important;
  line-height: 1 !important;
  cursor: pointer !important;
  border-radius: 3px !important;
  padding: 0 !important;
  margin: 0 !important;
  transition: all 0.15s ease !important;
}

.vscode-editor-body :deep(.cm-panel.cm-search button[name="close"]:hover) {
  background-color: rgba(255, 255, 255, 0.1) !important;
  color: #ffffff !important;
}

/* 匹配高亮项 */
.vscode-editor-body :deep(.cm-searchMatch) {
  background-color: rgba(234, 92, 0, 0.45) !important;
  border-radius: 2px !important;
}

.vscode-editor-body :deep(.cm-searchMatch.cm-searchMatch-selected) {
  background-color: #515c6a !important;
  outline: 1px solid #58a6ff !important;
}

/* 4. VS Code 标志性经典深天蓝底状态栏 (#007acc) */
.vscode-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #007acc;
  color: #ffffff;
  height: 24px;
  padding: 0 10px;
  font-size: 11px;
  user-select: none;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.status-section-left,
.status-section-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-item {
  display: inline-flex;
  align-items: center;
  color: #ffffff;
  cursor: default;
  transition: opacity 0.15s ease;
}

.status-item.branch-pill {
  font-weight: 600;
}

.status-item.lang-selector {
  font-weight: 600;
  padding: 1px 4px;
  border-radius: 2px;
  cursor: pointer;
}

.status-item.lang-selector:hover {
  background-color: rgba(255, 255, 255, 0.2);
}
</style>
