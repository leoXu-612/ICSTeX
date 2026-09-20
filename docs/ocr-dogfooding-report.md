# ICSTeX 公式 OCR Dogfooding 报告（真实材料）

> 目的：用真实教材/论文/手写与截图类材料走应用真实识别链路（`split_formula_lines` → `save_temp` → `_wait_ocr` → pix2tex 子进程），记录逐项结果。
> 环境：pix2tex venv（`/tmp/pix2tex_spike.xi2KZz/venv`），模型 manifest 位于 `~/Library/Application Support/ICSTeX/optional-tools/...`。

## 1. 材料来源

| 类别 | 材料 | 来源 |
| --- | --- | --- |
| 论文 | Attention Is All You Need（arXiv:1706.03762）真实公式 | https://arxiv.org/pdf/1706.03762 + https://arxiv.org/e-print/1706.03762 |
| 论文 | Deep Residual Learning（arXiv:1512.03385）真实公式 | https://arxiv.org/e-print/1512.03385 |
| 截图 | 上述论文 PDF 第 4 页公式区域真实裁剪 | `pdftotext -bbox` 定位 + `pdftoppm -x -y -W -H` 裁剪（300 DPI） |
| 手写 | CROHME HAMEX 真实手写轨迹（inkml）光栅化 | https://github.com/vndee/offline-crohme（`CROHME_labeled_2016/HAMEX/`） |

> 教材 PDF 说明：尝试了 MIT OCW、OpenStax、linear.ups.edu、APEX Calculus 等公开教材直链，均因网络不可达（DNS/超时）或 CDN AccessDenied 未能下载，本报告如实记为“教材材料受网络限制未纳入”。论文公式与真实 PDF 页面裁剪作为等价替代。

## 2. 结果

| # | 类别 | 图片 | 期望 | 状态 | 耗时 | 识别结果摘要 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 论文 | paper_attention.png | `Attention(Q,K,V)=softmax(QK^T/√d_k)V` | OK（语义错误） | 5.69s（含冷启动） | 结构近似：`\operatorname{Atterlion}(Q,K,V)={\mathrm{soflulax}}(\frac{...}{...})V`；softmax/QK^T 被误读 |
| 2 | 论文 | paper_multihead.png | `MultiHead(Q,K,V)=Concat(head_1,...,head_h)W^O` | OK（部分正确） | 0.52s | `\operatorname{MiuillilHead}(Q,K,V)=\operatorname{Concat}(\operatorname{head}_{1},\dots,\operatorname{head}_{h})W^{U}`；结构完整，拼写与 W 上标有误 |
| 3 | 论文 | paper_resnet.png | `y=F(x,{W_i})+x` | **OK（完全正确）** | 0.21s | `y={\mathcal{F}}(x,\{W_{i}\})+x` |
| 4 | 截图 | screenshot_attention-04.png | 论文真实页面公式区 | OK（含上下文） | 5.49s | 识别出周围正文（`into a matrix Q...`、`the matrix of outputs as`），公式本体被噪声阵列覆盖 |
| 5 | 手写 | phi(x) | `\phi(x)` | OK（错误） | 3.75s | 输出为噪声阵列，未识别出 φ(x) |
| 6 | 手写 | (t,x,y,z)=x^a | `(t,x,y,z)=x^a` | OK（错误） | 0.21s | `\omega+\phi\sigma^{2}`，完全误读 |
| 7 | 手写 | log 长公式 | `log_c(a-b)=...` | OK（错误） | 0.18s | `\varphi=\sin\varphi=\sin\varphi`，完全误读 |

原始 CSV：`/tmp/icstex_dogfood/dogfood-results.csv`（本机临时目录，可复现命令见 §4）。

## 3. 结论

1. **干净渲染的简单论文公式可识别**：ResNet 公式完全正确；MultiHead 结构完整、仅字母级误差；Attention 公式结构近似、符号误读较多。
2. **真实页面截图识别差**：裁剪区域含正文与噪声时，pix2tex 输出污染（巨阵/乱码），且本次裁剪无法做人工视觉核验，属于真实世界预期内的失败。
3. **手写公式基本不可用**：3 例均误读，与本项目此前的“pix2tex 面向印刷体”定位一致；手写场景应保留人工核对并明确提示。
4. **性能**：冷启动首图 ~5.7s，热推理 0.18–0.5s/图，与 spike 数据一致。
5. **产品含义**：批量窗口的“失败/低置信”可见性（本工单 #4）是必要兜底——用户必须能区分“识别到但可能错”与“没识别到/异常”。

## 4. 复现命令

```bash
mkdir -p /tmp/icstex_dogfood && cd /tmp/icstex_dogfood
# 论文 PDF / 源码
curl -sL -o attention.pdf https://arxiv.org/pdf/1706.03762
curl -sL -o attention_src.tar.gz https://arxiv.org/e-print/1706.03762 && tar -xzf attention_src.tar.gz
# 论文公式渲染（xelatex + sips）与截图裁剪（pdftoppm）
python3 render.py   # 见本次工单脚本
pdftotext -f 4 -l 4 -bbox attention.pdf - | ...   # 定位“compute the matrix of outputs as:”
pdftoppm -f 4 -l 4 -r 300 -png -x 380 -y 1780 -W 1240 -H 210 attention.pdf screenshot_attention
# 手写：CROHME INKML 光栅化
curl -sL -o phi.inkml https://raw.githubusercontent.com/vndee/offline-crohme/master/CROHME_labeled_2016/HAMEX/formulaire001-equation001.inkml
/tmp/pix2tex_spike.xi2KZz/venv/bin/python render_inkml.py phi.inkml
# 识别
ICSTEX_PIX2TEX_ENV=/tmp/pix2tex_spike.xi2KZz/venv python3 run_dogfood.py
```

## 5. 已知限制

- 本会话无图像预览能力，无法对裁剪区域做人工视觉确认（坐标基于 PDF 文本定位，可能含正文）。
- 教材 PDF 未纳入（网络受限）；建议后续在可达网络下补 OpenStax/OCW 教材页面裁剪。
- 手写样本来自 CROHME（研究用途），仅 3 例，结论为代表性观察而非统计结论。
