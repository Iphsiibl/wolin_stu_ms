/**
 * 应用入口
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import 'element-plus/dist/index.css'
// 暗黑模式变量（Geeker 模板的 element-dark.scss 依赖它）
import 'element-plus/theme-chalk/dark/css-vars.css'
// Geeker-Admin 样式层（reset / common / element / element-dark）
import '@/styles/index.scss'
// 项目补充样式与设计 token（要排在 element 之后才能覆盖）
import '@/styles/theme.css'
// 图标字体
import '@/assets/iconfont/iconfont.scss'

import App from './App.vue'
import router from './router'
import { DEFAULT_PRIMARY } from '@/config'
import { applyPrimaryColor } from '@/utils/color'
import { installConsoleLogger } from '@/utils/logger'

// 用 config 里的主色覆盖 Element Plus 的整套色阶，
// 这样改主色只需要改 src/config/index.ts 一处。
applyPrimaryColor(DEFAULT_PRIMARY)

// 把控制台输出、未捕获异常收进前端的「运行日志」面板。
// 必须在业务代码跑起来之前装好，否则最早的报错抓不到。
installConsoleLogger()

const app = createApp(App)

// 所有 Element Plus 图标全局注册，
// 后面在模板里就能直接用 <el-icon><Search /></el-icon>
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

app.mount('#app')
