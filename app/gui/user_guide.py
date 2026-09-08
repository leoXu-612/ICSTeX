from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTextBrowser, QVBoxLayout, QWidget


GUIDE_HTML = """
<h2>ICSTeX 新手导引</h2>
<h3>1. 第一次使用</h3>
<p>先安装完整 MacTeX、TeX Live 或 MiKTeX。ICSTeX 不内置 LaTeX 发行版；环境医生可以帮你检查缺少哪些工具。</p>
<h3>2. 推荐工作流</h3>
<ol>
  <li>从“新建项目”或“模板”开始。</li>
  <li>写正文时保持自动编译开启；大量粘贴或改表格时可切到手动编译。</li>
  <li>用“插入”工具生成图片、表格、链接、公式和列表。</li>
  <li>编译失败时先看“检查”和“错误”面板，不必直接读完整 log。</li>
</ol>
<p>公式编辑器中，Tab / Shift+Tab 切换结构，Enter 完成命令输入；“插入/替换公式”才会写入正文。
表格支持从当前单元格粘贴矩形数据、清空所选和撤销；缩小表格涉及已有数据时会先确认。取消对话框不修改文档。</p>
<h3>3. 模板共享</h3>
<p>可以把当前文档保存为个人模板，也可以导出模板发给同学。导出的模板是普通 .tex 文件。</p>
<h3>4. PDF 与提交</h3>
<p>双击当前版本的快速预览或正式 PDF，可通过 SyncTeX 定位原始源码；过期或正在重建时请等待更新。工具栏“同步 PDF”仍要求正式 PDF。</p>
<p>成功编译后使用“导出 PDF”生成最终提交文件；如果提示 PDF 可能不是最新，请先重新编译。</p>
<h3>5. 常见问题</h3>
<ul>
  <li>找不到编译器：打开环境医生，确认 latexmk/pdflatex/xelatex 是否存在。</li>
  <li>中文无法编译：试试 XeLaTeX 或“中文 XeLaTeX 文章”模板。</li>
  <li>图片不显示：确认图片已在 figures 文件夹，并使用相对路径。</li>
</ul>
"""


class UserGuideDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新手导引")
        self.resize(640, 520)
        layout = QVBoxLayout(self)
        title = QLabel("从 0 到提交：ICSTeX 使用导引")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(GUIDE_HTML)
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
