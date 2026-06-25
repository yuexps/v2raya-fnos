# v2rayA SQLite 订阅导入 Bug 修复总结

## 1. 问题现象
在新版 v2rayA 中（切换为融合内核或启用新版架构），导入订阅时前端提示成功，但实际并没有成功导入（前端订阅列表为空）。
同时后端服务打印如下警告日志：
```log
Backend: 2026/06/25 13:50:32.473  [W] [touch.go:70]  unsupported link type: 
```

---

## 2. 根本原因
在新版 v2rayA 中，数据库底层由原本的 **BoltDB** 重构为了 **SQLite**。但在编写 SQLite 的 list 操作适配代码时，引入了一个严重的 JSON 序列化缺陷：

1. **Bug 发生位置**：  
   在 [listOp.go](v2rayA/service/db/listOp.go) 的 `ListGet` 和 `ListGetAll` 中，针对 `touch/subscriptions`（获取订阅及关联节点）的读取逻辑：
   * 原代码使用 `[]gjson.Result` 切片来暂存各个节点的原始 JSON 数据。
   * 随后，原代码直接对该切片执行了 `jsoniter.Marshal(servers)`。

2. **为什么导致故障**：
   * `gjson.Result` 是用于只读解析的结构体，**并没有**实现 `json.Marshaler` 接口。
   * 直接序列化 `[]gjson.Result` 时，Go 的 JSON 库会以其原本的结构体成员进行序列化，将节点的 JSON 结构破坏性地重构为了类似 `[{"Type":3,"Raw":"{\"serverObj\":...}","Str":""}]` 这样的非预期对象。
   * 这导致调用者 [raw.go](v2rayA/service/db/configure/raw.go#L24) 在使用 `Bytes2SubscriptionRaw` 反序列化节点时，执行 `raw.Get("serverObj.protocol").String()` 无法定位到 protocol 字段，只能拿到**空字符串 `""`**。
   * 随后触发 `serverObj.New("")` 报错：`unsupported link type: `，导致整个订阅加载失败而被忽略，因此在前端列表中无法展示。

---

## 3. 修复方案
我们重构了 [listOp.go](v2rayA/service/db/listOp.go) 中对 `touch/subscriptions` 的反序列化与拼接逻辑：

* **避免二次序列化**：舍弃了将节点还原为 `gjson.Result` 并使用 `jsoniter.Marshal` 序列化的低效逻辑。
* **直接拼接**：将 `servers` 的暂存容器改为 `[]string` 存储原始 JSON 字符串，并通过 Go 原生的 `strings.Join(servers, ",")` 直接拼接出合法的 JSON 数组结构。
* **效果**：不仅完美修复了节点 protocol 丢失的 Bug，使得订阅能够正常导入与加载，同时也避免了频繁的 JSON 解析与再序列化开销，提升了列表拉取速度。

---

## 4. 影响范围
该 Bug 仅在新版 v2rayA 重构为 SQLite 存储时触发，与底层究竟运行 `xray`、`v2ray` 还是融合内核二进制无直接关系。以前正常导入是因为旧版仍使用 BoltDB 存储，重构为 SQLite 后统一受此 Bug 影响。
