---
name: v2raya-fnos-adapter
description: 适配并修补新版 v2rayA 后端 Go 服务和前端 GUI 项目，以支持 Unix Domain Socket (UDS)、动态 BaseUrl 前缀和默认端口启用逻辑，使其能平滑部署在飞牛 NAS 平台上。
---

# v2rayA 飞牛 NAS 应用适配修补指南

本指南用于指导 AI 在面对新版 v2rayA 源码时，如何智能且灵活地对其进行修补与适配，从而支持飞牛平台的 Unix Domain Socket (UDS)、`/app/v2raya` 反向代理子路径 (`BaseUrl`) 动态挂载，并默认只开启 `20172` 分流/混合代理端口。

---

## 1. 后端参数扩展 (EnvironmentConfig)

### 目标文件
`v2rayA/service/conf/environmentConfig.go`

### 修补任务
1. **新增命令行与环境变量支持**：
   在 `Params` 结构体中添加 `Socket` 与 `BaseUrl` 两个参数声明（`gonfig` 库会自动绑定 `V2RAYA_SOCKET` 与 `V2RAYA_BASEURL` 环境变量）：
   ```go
   Socket               string `id:"socket" desc:"Unix socket path for listening"`
   BaseUrl              string `id:"baseurl" default:"/" desc:"Base URL path prefix"`
   ```
2. **规范化 BaseUrl 逻辑**：
   在 `initFunc()` 进行环境加载后（例如在 `if params.ShowVersion` 判定之前），对 `params.BaseUrl` 进行标准化校验。确保其以 `/` 开头，且在不为根目录时去除末尾的 `/`：
   ```go
   if params.BaseUrl == "" {
       params.BaseUrl = "/"
   } else {
       if !strings.HasPrefix(params.BaseUrl, "/") {
           params.BaseUrl = "/" + params.BaseUrl
       }
       if params.BaseUrl != "/" {
           params.BaseUrl = strings.TrimSuffix(params.BaseUrl, "/")
       }
   }
   ```

---

## 2. 后端服务监听与路由组 (Router)

### 目标文件
`v2rayA/service/server/router/index.go`

### 修补任务
1. **修改 ServeGUI 方法签名**：
   将 `ServeGUI` 接收的参数类型从 `*gin.Engine` 泛化为 `gin.IRoutes`。以便其能够挂载至 `gin.RouterGroup` 路由组下。
2. **动态提取静态资源剥离前缀**：
   在 `ServeGUI` 方法内部，检测传入路由组的 BasePath 并动态拼接出 `staticPrefix`，用以传递给 `http.StripPrefix` 包裹静态文件服务。防止反代子路径下静态资源因丢掉 Base 前缀而报 404：
   ```go
   prefix := ""
   if group, ok := r.(*gin.RouterGroup); ok {
       prefix = group.BasePath()
   }
   staticPrefix := filepath.ToSlash(filepath.Join(prefix, "static"))
   if !strings.HasPrefix(staticPrefix, "/") {
       staticPrefix = "/" + staticPrefix
   }
   ss := http.StripPrefix(staticPrefix, statigz.FileServer(staticFS))
   ```
3. **路由组重构 (Run 方法)**：
   在 `Run()` 函数中，通过配置中读到的 `BaseUrl` 创建主路由组（`root := engine.Group(app.BaseUrl)`）。
   随后，将所有 API 路由组（`noAuth` / `auth`）以及 `ServeGUI` 统一挂载在 `root` 下，而不再直接挂在全局 `engine` 上。
4. **添加 Unix Domain Socket 监听支持**：
   在 `Run()` 的末尾，若 `app.Socket` 不为空：
   - 清除原有的冲突 socket 文件。
   - 通过 `net.Listen("unix", app.Socket)` 启动 UDS 监听。
   - 强行修改其权限为 `0777`（`os.Chmod(app.Socket, 0777)`）以确保反代网关能顺利读写。
   - 交由 `http.Serve` 承载，随后提前返回。
5. **消除冗余的 TCP 日志打印**：
   在 `ServeGUI` 方法的最末尾获取网卡并打印 TCP 监听地址前，如果 `app.Socket != ""`，直接提前 `return`。避免在纯 Unix Domain Socket 模式运行下，仍然输出一长串混淆的 `http://...:2017` 日志。

---

## 3. 后端默认端口配置修改 (Configure)

### 目标文件
`v2rayA/service/db/configure/configure.go`

### 修补任务
1. **修改默认端口初始化**：
   在 `New()` 函数中，将默认端口中的 `Socks5` 和 `Http` 初始化置为 `0`（禁用状态），仅保留 `HttpWithPac` 默认在 `20172` 上启动。
2. **修改默认端口 Null 恢复逻辑**：
   在 `GetPortsNotNil()` 方法中，将 `p == nil` 时新建 Ports 的默认赋值同样改为 `Socks5` 和 `Http` 为 `0`，`HttpWithPac` 保持为 `20172`。

---

## 4. 传统前端隐藏路径与 WebSocket 修复 (GUI)

### 目标文件
* `v2rayA/gui/src/App.vue`
* `v2rayA/gui/src/plugins/backendPort.js`
* `v2rayA/gui/src/components/modalCustomPorts.vue`
* `v2rayA/gui/src/locales/zh.js`与`en.js`

### 修补任务
1. **修复 WebSocket 子路径丢失问题**：
   在 `connectWsMessage()` 函数合成消息中心连接的 `ws` 或 `wss` 链接时：
   不能再使用硬编码根路径的 `url = "${protocol}://${u.host}:${u.port}/api/message..."`。
   Need to extract the base prefix (e.g. `/app/v2raya/api` -> `/app/v2raya`) from `u.path` and concatenate it, to ensure connection stays alive:
   ```javascript
   let basePath = u.path;
   if (basePath.endsWith("/api")) {
     basePath = basePath.slice(0, -4);
   }
   url = `${protocol}://${u.host}:${u.port}${basePath}/api/message?Authorization=${encodeURIComponent(localStorage["token"])}`;
   ```
2. **修复 API 基准路径丢失问题**：
   在 `backendPort.js` 中，如果在反代子路径下运行，需要在初始化时根据 `window.location.pathname` 智能提取出反代路径前缀写入 `backendAddress` 中，以防止 AJAX 请求返回 404：
   ```javascript
   let ba = localStorage.getItem("backendAddress");
   let currentPrefix = "";
   if (typeof window !== "undefined") {
     let path = window.location.pathname;
     const match = path.match(/^(.*)\/(?:login|setting|log|server|rule|running)?\/?$/);
     if (match) {
       currentPrefix = match[1];
     }
   }
   if (currentPrefix && currentPrefix !== "/") {
     localStorage.setItem("backendAddress", currentPrefix);
   } else {
     if (ba == null) {
       localStorage.setItem("backendAddress", "");
     }
   }
   ```
3. **禁用前端手动修改服务端地址**：
   在 `modalCustomPorts.vue` 中，将服务端地址的 `b-input` 输入框设为 `disabled` 只读展示，防止用户误改毁坏连接：
   ```vue
   <b-input
     ref="backendAddress"
     v-model="table.backendAddress"
     placeholder="http://localhost:2017"
     pattern="https?://.+(:\d+)?"
     disabled
   >
   ```
4. **修改相关的多语言提示信息**：
   在语言包文件 `zh.js` 和 `en.js` 中，把 `customAddressPort.messages` 数组下的第一条提示（通常用于说明如何通过环境变量或参数更改地址）修改为飞牛平台托管说明：
   * 中文（`zh.js`）：`"在飞牛 NAS 平台上，服务端地址已由系统自动配置与接管，禁止手动修改。"`
   * 英文（`en.js`）：`"On FN-OS, the service address is automatically configured by system and editing is disabled."`
5. **专版关于（About）弹窗内容修改**：
   在多语言包的 `about` 属性中，清除原版关于已禁用的 SOCKS（20170）、HTTP（20171）等默认端口的混淆描述。改为明确标示本版本为 **飞牛 NAS 专用版 (Linux x86_64 / aarch64)**，采用 UDS 通信零管理 TCP 端口占用，且仅默认启用 `20172` 分流代理端口。

---
