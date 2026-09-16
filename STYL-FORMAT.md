# 苹果地图 .styl 样式表格式（2026-09-16 数据会话，限时 4 小时探测的结果）

结论先行：**格式已解开，球文件的颜色/线宽/字号已全部读出**（2421 个样式、3115 个属性集，逐位解到块尾只剩 1–2 个填充位）。解码器在 `pipeline/basemap/styl/styl_decode.py`，数值表在 `basemap/data/styl/globe-key-numbers.tsv`（已提交）和 `basemap/data/styl/*.tsv|json`（全量，本地生成不提交）。
卡住的只剩两样：① 属性编号→人类可读名只定了一半（见第五节）；② 球的海面/陆地底色**不在样式表里**——球文件没有任何面填充样式，海色是贴图/栅格，样式表只管球上的标注、线、边界（第六节）。

样本：`~/Money/styl-work/*.styl`（本机 `~/Library/Caches/GeoServices/Resources/`，不进仓库）。依据：本机 macOS 27 的 VectorKit 二进制（从 dyld 共享缓存抽出，带符号：`gss::StyleSheet<gss::PropertyID>::decodeStyl`、`geo::ibitstream`、64 个 `gss::xxxDecoder`）+ 验收会话拉的 iOS 26.1 反编译（`~/Money/styl-work/vk/VectorKit_09/10/11/12/13/14.mm`）。样式语言叫 **GeoCSS**（命名空间 `gss`），`.styl` 是编译产物。

## 一、容器（定死）

```
'STYL'  u16 章数(=5)  然后每章 14 字节：u16 章号  u32 起  u32 止  u32 解压后长度
```
起/止是文件内字节偏移，每章一段 zlib 流（`78 9c`）。章号固定：

| 章号 | 内容 | 球文件解压后 | 解到哪 |
|---|---|---|---|
| 1 | stylesheet info：版本、模式、属性编码表、**属性尺寸表** | 647 B | 全解 |
| 10 | global properties：引擎参数（三角宽、交通最低缩放、导航距离档…） | 22 B | 大半解，无颜色 |
| 20 | property sets：3115 个属性集（真正的数值都在这） | 53 KB | 全解 |
| 21 | styles：2421 个样式（名字、继承、按缩放/条件引用属性集） | 148 KB | 全解 |
| 30 | style matching tree：要素属性→样式的匹配树 | 22 KB | 未解（结构见第七节） |

同一版本 hybrid 与 globe-default 逐字节相同；1x 与 @2x 的差只在 20/21 章的数值（不是简单翻倍，是另一套设计值，见第四节）。

## 二、位流原语（`geo::ibitstream`，MSB 先）

- `bits(n)`：MSB 先取 n 位——标志位、计数、字符、16 位定点（大端）。
- `uint(n)` = `readUIntBits`：先取 n//8 个整字节按**小端**拼，再取 n%8 位作最高的半字节。9 位数 = 1 字节 + 1 位。
- `varint`：LEB128，每组 8 位（7 位数据 + 续位），最多 10 组。
- `string`：8 位字符到 NUL，起点可以不对齐——这就是为什么 `strings` 只找得到零星串、大量串是错位的。
- `float32`：4 字节小端。
- 「位数字段」一律 5 位存 (n−1)。

## 三、各章结构

### 1 章 stylesheet info
```
varint 版本(=14)  1 位 debug  8 位 模式数(3)  每模式 1 位支持标志
u16 属性数(100)  5 位 要素属性位数-1(8)  5 位 客户端属性位数-1(8)
每属性：1 位 是否要素属性  →1: uint(要素位数) 编号 / 0: uint(客户端位数) 编号+0x10000   5 位 该属性取值位数-1
5 位 属性编号位数-1(9)  uint(9) 属性数(210)
每属性：uint(9) 编号  2 位 kind  kind 0/1 再跟 varint 尺寸
   kind 0 = 尺寸单位 位   kind 1 = 尺寸单位 字节   kind 2 = 固定 1 位（布尔）   kind 3 = 变长，值前有 varint 字节数
```
### 20 章 property sets
```
5 位 属性集索引位数-1(12)  uint(12) 属性集数(3115)
每集：uint(9) 属性个数  每属性：uint(9) 编号  [kind 3: varint 字节数]  值（按 1 章的尺寸）
```
读完一个值，游标**强制**跳到 起点+尺寸（解码器多读少读都不影响下一个）。
### 21 章 styles
```
6 个 5 位：继承表长位数、缩放段数位数、条件样式数位数、条件数位数、条件取值数位数、样式数位数（球：3,6,6,3,8,12）
uint(样式位数) 样式数
每样式：string 名字  varint score  uint(继承位数) 父样式数 + 各 uint(样式位数) 父索引
        uint(集位数) 基础属性集
        uint(缩放位数) 段数 + 每段 8 位 zmin×8, 8 位 zmax×8, uint(集位数) 属性集
        uint(条件样式位数) 条件样式数 + 每个：uint(条件位数) 条件数 + 每条件 [属性编码同 1 章][uint(取值数位数) 个值，每值 uint(该属性取值位数)]
                                          uint(集位数) 属性集 + 缩放段列表（同上）
```
一个样式的缩放段可以重叠（同一样式里三组 z0–24 各管不同属性，如 Border-Country-NonDisputed-Colors-Globe 有 18 段）；运行时函数叫 `hasValueForKeyAtZAtEnd`，推测**后者覆盖前者**，未验证。

### 值类型（`gss::xxxDecoder`，按属性编号查表 `decoder_table.py`）
| 类型 | 位数 | 解法 |
|---|---|---|
| rgba8 | 32 | 4 字节顺序 **A,B,G,R**（sRGB 8 位）。反汇编：4 字节按流序存 u32 → `rev` → 拆 (b3,b2,b1,b0)/255 → `geo::Color(r,g,b,a)`；geo::Color 通道序用 kDefault 常量核过（交通 Stopped=(65535,6425,7710)红、Fast=(13107,48059,0)绿）。运行时再转线性 16 位/通道 |
| float | 32 | 小端 float32 |
| floatPair | 64 | 两个 float32 |
| bool | 1 | |
| uint32 / 各枚举 | n | `uint(n)`，n 来自 1 章尺寸表（枚举 2–9 位） |
| int32 / uint64 / uint8 | 32/64/8 | 小端 |
| fixedPoint12_4 / 8_8 | 16 | 大端 16 位 ÷16 / ÷256 |
| fixedPoint5_3 / 6_2 / 0To1 / 0to2_55 / 8_0 | 8 | ÷8 / ÷4 / ÷255 / ÷100 / 原值 |
| string | 变长 | kind 3，字节数 varint 在前，含 NUL；长度 0 = 空串 |
| labelInfo（172） | 变长 | 7 个「1 位有无 + 值」：height(f32)、heightCurve(3 位)、heightCurveLimit(f32)、haloSize、fontExpansion、spacing、arrowHeight(各 f32)。**height 就是标注字号 pt**（Country-Label-Extra-Large 13→16→20，Continent 9→14→20），1122 处，比属性 21 常用 |
| traffic（90–93 = Stopped/Slow/Medium/Fast） | 变长 | 12 个「1 位有无 + 值」：visibility、fillColor、secondaryColor、pillMiddleLength、pillSpacing、secondaryWidth、width、minWidth、secondaryMinWidth、maxWidth、secondaryMaxWidth、gradientMaskColor；球文件只出现 fillColor（暗红 (104,23,37)/红 (239,56,57)/黄 (255,201,23)/蓝 (17,151,255)） |
| dashPattern / iconGradient / animationCurve / genericShieldStyle | 变长或定长 | 未解，当 raw 跳过 |

实证：Route-Line-Base-Light 属性 1 = rgb(0,162,255)（苹果路线蓝）；Ocean-Label-Color-Dark-Base 属性 24 z2–4 = rgb(62,116,182)，验收会话量具实测暗色海洋标注 #3d73b6=(61,115,182)，差 1。

## 四、1x 与 @2x

不是尺寸翻倍。逐行比对（`globe-default-20207` vs `21097@2x`，20 843 行）：值不同的主要是属性 18（float，标签字号系数，×0.85/×1.17）、3（线宽，×0.8/×0.5/×1.08…）、6（描边宽，×2/×0.8）、384（×2）、125 图标尺寸档；@2x 多出 1002 行（图标缩放 456、labelInfo 172、图标尺寸 125）。两份都要留。

## 五、属性编号→名字（`property_names.py` 定死的 + `inferred_names.py` 推的）

进度（球文件实际用到 210 个属性）：**kDefault 定死 64 + 按调用方/样式名/值推出 36 = 100/210**；剩 110 个多是用一两次的布尔/枚举，推名对数值表意义不大。全表 425 个有映射的属性里 kDefault 定死 144。

两套编号：**.styl 流里的编号（0–496）≠ 代码里的 `gss::PropertyID`**，中间有一张 u16 重映射表（27 版 VectorKit `0x1c354a768`，流 2→PropertyID 93）。验收会话的 `prop_callers.txt` 键是 PropertyID，已按重映射转成流编号（`callers_by_stream_id.tsv`），26.1 调用点的取值类型与 27 解码表 0 冲突。

已定名 144 个（`gss::defaultValueForKey<PropertyID,T>` 在进程内逐编号调用，返回常量地址对符号名 `kDefaultXxx`）：25 haloColor、32 labelSpacing、42 arrowSpacing、45/46 arrow 色、70–74 margin、85/86 建筑色、87 trafficWidth、100–103 标签朝向/布局/图标样式、106/107 图标字形/光晕色、125 iconSize、187/188 文字位置、189–195 盾牌间距、221 curbColor、253/255/256 亮度、463–492 各 LumAdjustment、485/486 halo…
推出来的 36 个在 `inferred_names.py`，每个带证据和把握度（high/mid/low）。high 的：**1 fillColor**（802 处，路线蓝在这）、**2 strokeColor**、**3 width**（getRoadWidths/halfWidthAtZoom 读它）、**6 strokeWidth**（描边/套边宽）、**21 fontSize**（uint，8/12/13/18/20 pt）、**22 iconName**、**23 fontSpec**（"%$default,semibold,width=90"）、**24 textColor**（LabelCoreStyleGroup 读，暗色海洋标注对上实测）、**25 textHaloColor**、**55/57 coastlineGlowWidth/Color**（只在 Coastline-Glow-*，亮色 rgb(135,221,251) 对验收渲染的近岸浅水带 #88d4f5）、**203 gridColor**（只在 Grid-GlobeHybrid，混合球的经纬网）、**172 labelInfo**（已拆，height = 标注字号）、**0 visible**（False 即隐藏：国界 z0–2、洲名 z3+）、**90–93 trafficStopped/Slow/Medium/Fast**。mid/low 的：13/15 渲染顺序、18 textSizeScale、9/29/127 字号参数、41 arrowSize、210–212 route line scale 等。客户端属性 37 = IncreaseContrast（=1 时白天标注变纯黑+白光晕、字号 ×1.25）。
要素属性编号 1 起对 VectorKit 的名字表（1 LineType、4 Country 8 位、5 FeatureType、6 PoiType 9 位，位数吻合）；客户端属性 0x10000+ 只前三个对得上（MapMode 3 位、TimePeriod 1 位、SelectionState 2 位），后面枚举有洞，表里保留原编号。

## 六、球的底色不在这里（要点）

球文件 2421 个样式按前缀：POI 616、PhysicalFeature 300、Line 106、Globe(-Roads) 97、Route 87、City/CapitalCity 123、Border 27、Ocean 28、Rivers 31、Coastline 8……**没有一个面填充样式**（平面 default-56689.styl 有 11 293 个样式，含 Landcover-Water-*、LandPolygon-*、WaterPolygon-*、ParkPolygon-* 等）。
- 平面亮色水面：Landcover-Water-Explore-Light-Base 属性 1 = rgb(141,213,246) z0–4 / (136,217,246) z4–5 / (141,220,247) z5+；暗色 (33,57,130) / (31,54,122)。
- 量具的分深度海色（`ui/basemap/palette-ocean.json`，亮 (108,201,250)→(13,141,230)、暗 (23,43,104)→(0,13,34)）用 `match_palette.py` 对球文件和平面文件所有 rgba8（容差 12）：亮色档全部落空或只碰到无关的路线/POI 色，暗色档碰到的是标注光晕/河流描边（Rivers-Dark、Ocean-Label halo (19,31,73)、Geolines）——都不是面填充。深度分层是渲染器的海底贴图/明暗，不是样式表颜色。
- 所以球的海/陆是渲染器自己的贴图（NATIVE-RENDER 已记：球只在私有实现里），样式表管不到；要球的底色仍走「渲染器当量具」采样。scene-*.styl（ScenePropertyID）解开是 299 个相机/光照样式，也无颜色。

## 七、没做完的

1. 30 章匹配树：位流字段顺序已知（端链数位数、端链长位数、属性取值数位数、节点索引位数、子节点数位数、块尺寸位数 → 端链 → 节点：是否终端、样式索引/端链索引、未定义节点、子节点[属性值→子索引]），没写解码器。不解它也能用：样式名本身就是语义。
2. 复合类型 dashPattern/iconGradient 的内部布局（labelInfo、traffic 已拆）。
3. 10 章后半（road sign height 等 float 字段宽度有一处对不上）。
4. 属性定名剩 ~90 个无线索编号：验收会话的 `unnamed_globe_props.txt`（样式名×次数）可继续推；终审是改值渲染（验收会话在做）。
5. 值得不值得再投：格式层面**不用再投**（已到数值）；定名再投 1–2 小时能把常用 30 个定死；球底色不要在样式表上花时间。

## 八、怎么用 / 怎么验

```bash
python3 pipeline/basemap/styl/styl_decode.py ~/Money/styl-work/globe-default-20207.styl            # 概要与块尾剩余位
python3 pipeline/basemap/styl/styl_decode.py FILE.styl --show Ocean-Label-Color-Dark-Base          # 看一个样式
python3 pipeline/basemap/styl/styl_decode.py FILE.styl --color 61,115,182 8                        # 反查颜色
python3 pipeline/basemap/styl/styl_decode.py FILE.styl --tsv basemap/data/styl/globe-default-20207.tsv
python3 pipeline/basemap/styl/globe_numbers.py basemap/data/styl/globe-default-20207.tsv basemap/data/styl/globe-key-numbers.tsv
python3 pipeline/basemap/styl/match_palette.py ../transit-ui/ui/basemap/palette-ocean.json FILE.styl --tol 12   # 量具海色 vs 样式表颜色
```
验收三个抽查点（都能回到原始文件）：① `--show Route-Line-Base-Light` 属性 1 = rgb(0,162,255)；② `--show Ocean-Label-Color-Dark-Base` 属性 24 z2–4 = rgb(62,116,182) 对实测 #3d73b6；③ `--show Border-Country-NonDisputed-Base` 线宽 z0–2 0.9 → z12–14 2.1（`globe-key-numbers.tsv` 同行）。计数：属性集 3115、样式 2421、20 章剩 1 位、21 章剩 2 位。

全量表（`*.tsv`/`*.json`，20 MB）是苹果样式的逐值导出，仓库公开，**没提交**（.gitignore），本地一条命令重生成；只提交了 `globe-key-numbers.tsv`（4611 行，球相关样式的颜色/线宽/字号）——要不要连全量一起进仓库由验收定。
