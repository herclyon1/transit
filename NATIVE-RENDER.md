# 原生样式的捷径：让 Mac 自带的渲染器出图（2026-09-16 验收会话实测）

## 结论

不用从零仿。macOS 的 MapKit 有 `MKMapSnapshotter`，在本机用地图 App 同一套渲染器（VectorKit）把任意经纬度范围渲染成图片，**输出就是原生样式**：山影、海深分层、深海沟名、SF 字体、道路盾牌、地标图标全有。
实测（本机，`pipeline/basemap/snap.swift`）：
- 东亚 ll=30,125 spn=50,60 @1280×744：和地图 App 窗口同视野截图一致（只差球面，App 是球、快照是平面）。
- 大阪市 ll=34.69,135.50 spn=0.12,0.2：市区级完整。
- 暗色：`NSAppearance(named: .darkAqua)` 生效。
- 日文标注：进程参数 `-AppleLanguages '(ja)'` 生效（zh-Hans 同理，未测）。
- 一张 512×512 瓦片 0.84 s（`elevationStyle: .realistic`）。

网页版 maps.apple.com（MapKit JS 6.0.128）**不是**这套样式：平面、无海深、无山影、标注稀，当不了参照。

## 球只在苹果自己的地图 App 里有（11:11 实测）

公开的实时地图视图 `MKMapView`（`pipeline/basemap/mapview.swift`，开一个 1280×744 窗口截图）缩到全球（span 140×200）**仍是平面**，和快照一样。球体是地图 App 用私有技术画的，开发者接口拿不到。所以：
- 原生 App 的球，任何路线都复制不到原样；MapLibre 的球是把苹果画好的平面图贴到球面上，形似，但没有大气光晕、标注会随球面变形。
- 「像」的上限：平面视图（国家级到街区级）可以一模一样；全球视图只能形似。

## 用法

```
swiftc -O pipeline/basemap/snap.swift -o /tmp/snap
/tmp/snap <lat> <lng> <dlat> <dlng> <宽> <高> <输出.png> [dark] [-AppleLanguages '(ja)']
```

## 方案：预渲染栅格瓦片 + MapLibre 球面

1. 按 XYZ 瓦片格网（Web Mercator）逐块调用快照器，输出 512 px 瓦片，存 `tiles/apple/{light,dark}/{z}/{x}/{y}.webp`。
2. MapLibre（仓库已是 5.6.0）`projection: globe` + raster source。球面、缩放、我们自己的矢量叠加层（车站点、tiers 面、边界 pmtiles）都在上面。
3. 范围：东亚 z3–7 全覆盖（几百张）；日本 z8–10（几千张）；大阪府 z11–14（估 5–8 千张）。z15+ 不做，或只做大阪市。

## 已知代价（做之前用户拍板）

- **许可**：Apple 开发者协议禁止缓存/预渲染 Maps 内容离线分发。个人非商业站放 GitHub Pages 属于灰区，风险自担。
- **标注烤死在图里**：语言渲染时定死（每种语言一套瓦片）；「考我」模式要藏标签做不到，那一模式换无标注底图（现有 MapLibre 样式去掉 label 层）。
- **瓦片接缝**：每块单独渲染，标注避让各算各的，接缝处可能有半个字或重复字。缓解：一次渲染 3×3 块再切中间块。
- **体积**：512 px PNG 一张 100–400 KB；改 WebP 后大阪 z14 一套约 1 GB 以内，GitHub Pages 单仓上限 1 GB，暗色再翻倍，可能要放别处。

## 第 0 步（小）

数据会话：只渲染大阪市 z12 一层（约 100 张），MapLibre 空白页 + 球面 + 这层栅格，开到 ll=34.69,135.50 截图；验收拿地图 App 同视野截图并排。回答一个问题：接缝和清晰度能不能接受。能，再往外扩范围和层级。
