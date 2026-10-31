<template>
  <div class="yaml-editor-wrapper" :class="{ 'is-fullscreen': isFullscreen }">
    <!-- 顶部代码编辑器工具条 -->
    <div class="editor-header-bar">
      <div class="bar-left">
        <span class="lang-tag">YAML</span>
        <span class="editor-tip-text">代码编辑器已就绪 · 支持语法高亮与折叠</span>
      </div>

      <div class="bar-right">
        <!-- 统计信息 -->
        <div class="editor-stats-badge">
          <span>{{ lineCount }} 行</span>
          <span class="dot-sep">·</span>
          <span>{{ charCount }} 字符</span>
        </div>

        <!-- 换行切换 -->
        <button
          type="button"
          class="bar-btn"
          :class="{ active: isWrapLines }"
          :title="isWrapLines ? '已开启自动换行 (点击切换为横向滚动)' : '已关闭自动换行 (点击开启换行)'"
          @click="toggleWrapLines"
        >
          <el-icon><Operation /></el-icon>
          <span>{{ isWrapLines ? '自动换行' : '单行滚动' }}</span>
        </button>

        <!-- Tab 校验修复 (检测是否有制表符) -->
        <button
          v-if="hasTabChars"
          type="button"
          class="bar-btn warning-btn"
          title="检测到内容含有 Tab 制表符（YAML 语法禁止 Tab），点击一键转换为 2 空格"
          @click="fixTabsToSpaces"
        >
          <el-icon><MagicStick /></el-icon>
          <span>修复 Tab (转2空格)</span>
        </button>

        <!-- 一键复制 -->
        <button
          type="button"
          class="bar-btn"
          title="复制全部 YAML 源码"
          @click="handleCopyCode"
        >
          <el-icon><DocumentCopy /></el-icon>
          <span>复制</span>
        </button>

        <!-- 全屏切换 -->
        <button
          type="button"
          class="bar-btn"
          :title="isFullscreen ? '退出全屏' : '全屏编辑'"
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

    <!-- CodeMirror 核心编辑区 -->
    <div class="editor-container" ref="containerRef">
      <codemirror
        v-model="internalValue"
        :placeholder="placeholder"
        :style="{ height: isFullscreen ? 'calc(100vh - 120px)' : height }"
        :autofocus="false"
        :indent-with-tab="false"
        :tab-size="2"
        :extensions="editorExtensions"
        @change="handleCodeChange"
        @ready="handleEditorReady"
      />
    </div>

    <!-- 底部状态栏 -->
    <div class="editor-footer-bar">
      <div class="foot-left">
        <span class="foot-item">光标: 行 {{ cursorInfo.line }}, 列 {{ cursorInfo.col }}</span>
        <span class="foot-item">编码: UTF-8</span>
        <span class="foot-item">缩进: 2 空格</span>
      </div>
      <div class="foot-right">
        <span class="kbd-tip"><kbd>Ctrl</kbd> + <kbd>F</kbd> 查找/替换</span>
        <span class="kbd-tip"><kbd>Ctrl</kbd> + <kbd>Z</kbd> 撤销</span>
        <span class="kbd-tip"><kbd>Tab</kbd> 智能缩进</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, shallowRef, onBeforeUnmount } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { yaml } from '@codemirror/lang-yaml'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView, keymap, lineNumbers, highlightActiveLineGutter, highlightActiveLine } from '@codemirror/view'
import { EditorState, Compartment } from '@codemirror/state'
import { defaultKeymap, indentWithTab, history, historyKeymap } from '@codemirror/commands'
import { searchKeymap, highlightSelectionMatches } from '@codemirror/search'
import { bracketMatching, foldGutter, foldKeymap, indentUnit } from '@codemirror/language'
import { ElMessage } from 'element-plus'
import {
  Operation,
  DocumentCopy,
  FullScreen,
  Aim,
  MagicStick
} from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
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

watch(() => props.modelValue, (newVal) => {
  if (newVal !== internalValue.value) {
    internalValue.value = newVal || ''
  }
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

// 自定义暗黑主题微调（与 3X-UI 科技深色弹窗底色融合）
const customDarkTheme = EditorView.theme({
  '&': {
    backgroundColor: '#181a20',
    color: '#e2e8f0',
    fontFamily: 'Consolas, Monaco, "Courier New", monospace',
    fontSize: '13px'
  },
  '.cm-content': {
    caretColor: '#38bdf8',
    padding: '10px 0'
  },
  '&.cm-focused .cm-cursor': {
    borderLeftColor: '#38bdf8',
    borderLeftWidth: '2px'
  },
  '&.cm-focused .cm-selectionBackground, ::selection': {
    backgroundColor: 'rgba(56, 189, 248, 0.28) !important'
  },
  '.cm-gutters': {
    backgroundColor: '#14151b',
    color: '#64748b',
    borderRight: '1px solid #232631',
    paddingRight: '6px'
  },
  '.cm-activeLineGutter': {
    backgroundColor: '#20232d',
    color: '#38bdf8'
  },
  '.cm-activeLine': {
    backgroundColor: 'rgba(255, 255, 255, 0.03)'
  },
  '.cm-foldPlaceholder': {
    backgroundColor: '#252936',
    border: '1px solid #3b4254',
    color: '#94a3b8',
    borderRadius: '3px',
    padding: '0 6px',
    margin: '0 4px'
  },
  '.cm-scroller': {
    overflow: 'auto',
    fontFamily: 'Consolas, Monaco, "Courier New", monospace'
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

// Tab 按键行为拦截（保证插入 2 个空格而不是 \t）
const customIndentKeymap = keymap.of([
  {
    key: 'Tab',
    run: (view) => {
      view.dispatch(view.state.replaceSelection('  '))
      return true
    }
  }
])

// 组合扩展列表
const editorExtensions = computed(() => {
  return [
    lineNumbers(),
    highlightActiveLineGutter(),
    highlightActiveLine(),
    history(),
    foldGutter(),
    bracketMatching(),
    highlightSelectionMatches(),
    indentUnit.of('  '),
    yaml(),
    oneDark,
    customDarkTheme,
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

// 检测是否含有 Tab 制表符
const hasTabChars = computed(() => {
  return (internalValue.value || '').includes('\t')
})

// 一键将 Tab 制表符替换为 2 空格
const fixTabsToSpaces = () => {
  if (!internalValue.value) return
  const fixed = internalValue.value.replace(/\t/g, '  ')
  internalValue.value = fixed
  emit('update:modelValue', fixed)
  emit('change', fixed)
  ElMessage.success('已成功将所有 Tab 制表符替换为 2 个标准空格')
}

// 切换自动折行
const toggleWrapLines = () => {
  isWrapLines.value = !isWrapLines.value
  if (viewRef.value) {
    viewRef.value.dispatch({
      effects: wrapCompartment.reconfigure(isWrapLines.value ? EditorView.lineWrapping : [])
    })
  }
}

// 复制源码
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
    ElMessage.success('YAML 源码已成功复制到剪贴板')
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
.yaml-editor-wrapper {
  display: flex;
  flex-direction: column;
  background-color: #181a20;
  border: 1px solid #282c37;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
  transition: all 0.2s ease;
}

/* 全屏模式样式 */
.yaml-editor-wrapper.is-fullscreen {
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

/* 顶部操作条 */
.editor-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #1f222b;
  border-bottom: 1px solid #282c37;
  padding: 8px 14px;
  user-select: none;
}

.bar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.lang-tag {
  background: linear-gradient(135deg, #1e40af, #2563eb);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  letter-spacing: 0.5px;
  box-shadow: 0 0 8px rgba(37, 99, 235, 0.4);
}

.editor-tip-text {
  font-size: 12px;
  color: #94a3b8;
}

.bar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.editor-stats-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #15171d;
  border: 1px solid #282c37;
  border-radius: 4px;
  padding: 3px 9px;
  font-size: 11px;
  color: #94a3b8;
  font-family: Consolas, Monaco, monospace;
}

.dot-sep {
  opacity: 0.5;
}

.bar-btn {
  background: #262934;
  border: 1px solid #333846;
  color: #cbd5e1;
  border-radius: 4px;
  font-size: 12px;
  padding: 4px 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.bar-btn:hover {
  background: #2e3342;
  border-color: #475569;
  color: #ffffff;
}

.bar-btn.active {
  background: rgba(56, 189, 248, 0.15);
  border-color: #38bdf8;
  color: #38bdf8;
}

.bar-btn.warning-btn {
  background: rgba(245, 158, 11, 0.15);
  border-color: #f59e0b;
  color: #fbbf24;
  animation: pulse-border 1.5s infinite;
}

@keyframes pulse-border {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4);
  }
  50% {
    box-shadow: 0 0 8px 1px rgba(245, 158, 11, 0.5);
  }
}

/* 核心编辑区 */
.editor-container {
  flex: 1;
  width: 100%;
  overflow: hidden;
  position: relative;
}

/* 深度适配 CodeMirror 内部样式 */
.editor-container :deep(.cm-editor) {
  height: 100%;
  outline: none !important;
}

.editor-container :deep(.cm-scroller) {
  line-height: 1.55;
}

/* 底部状态栏 */
.editor-footer-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #16181f;
  border-top: 1px solid #232631;
  padding: 5px 14px;
  font-size: 11px;
  color: #64748b;
  user-select: none;
}

.foot-left {
  display: flex;
  align-items: center;
  gap: 14px;
  font-family: Consolas, Monaco, monospace;
}

.foot-item {
  color: #8b949e;
}

.foot-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.kbd-tip {
  color: #64748b;
  font-size: 11px;
}

.kbd-tip kbd {
  background: #242733;
  border: 1px solid #333846;
  border-radius: 3px;
  padding: 1px 4px;
  color: #cbd5e1;
  font-size: 10px;
  font-family: inherit;
}
</style>
