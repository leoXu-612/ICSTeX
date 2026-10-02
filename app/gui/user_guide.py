from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QMessageBox, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout, QWidget

from app.gui.assets import asset_path
from app.gui.responsive.helpers import ButtonFlowLayout
from app.gui.theme import PRIMARY_BUTTON_STATE_STYLE


GUIDE_PAGES = (
    ("先试一遍", "edit-title.png", "练习副本中的标题。只替换选中的文字，保留两边的大括号。", r"""
<h2>先改一个标题，看看 PDF 怎么变</h2>
<p>第一次点“开始练习”，之后点“继续上次练习”。示例会在单独窗口打开，原来的文稿和编辑设置不会改变。</p>
<ol><li>选中示例标题，换成你自己的标题。</li>
<li>点“正式编译”，把文字排成 PDF。</li>
<li>在 PDF 中找到新标题，再点“我看到了新标题”。</li></ol>
<p>练习中可以随时“收起导引”。回来时，从“帮助 → 新手导引”继续。
内容会保留；如果关闭过练习窗口，需要再编译一次，核对当前内容。</p>
<h3>还没有 LaTeX 环境？</h3>
<p>你仍然可以创建和编辑文件。生成 PDF 前，需要安装 MacTeX、TeX Live 或 MiKTeX。
回到欢迎页点“查看安装指引”，也可以从“帮助”菜单打开环境医生。软件不会自动安装这些工具。</p>
"""),
    ("写作和预览", "write-preview.png", "左边是可编辑的 .tex，右边是编译后的 PDF；右侧标题与左侧修改对应。", r"""
<h2>平时怎么写</h2>
<p>点“新建项目”，选写作语言和模板，再选保存位置。中文写作可以用“中文 XeLaTeX 文章”，
高级设置里的编译器保留“自动选择（推荐）”。已有文件夹不会被覆盖。</p>
<p>左边编辑 <code>main.tex</code>，右边看排版。第一次请主动点“正式编译”。
开启“自动快速预览”后，后续改动会在你停笔、自动保存后更新 PDF。</p>
<p>顶部按“文件、编译 / 输出、视图”分组。点“项目导航”查看左侧的文件、大纲和写作工具；
下方“控制台”放日志、错误、字数和检查。拖动分隔线调整阅读空间，正常退出后会记住源码/PDF比例和控制台高度。
项目状态在工具栏下一行，“项目操作”提供当前项目的相关入口。</p>
<h3>这三个状态要分开看</h3>
<p><b>文档已保存</b>：文字已经写进 .tex 文件，不代表 PDF 已更新。<br>
<b>PDF 已是最新 / 快速预览 · 当前版本</b>：当前内容已编译完成。<br>
<b>当前显示旧版本 / 旧预览</b>：你看到的仍是之前成功生成的页面。</p>
<p>快速预览可能使用较小的图片。检查原图质量时点“正式编译”。
把光标放在源码中，点“定位 PDF”就能在最新的快速预览或正式 PDF 中找到对应位置，不必为定位再编译一次。
双击当前 PDF 的文字可以回到源码。窗口较窄时，“定位 PDF”会自动切换到 PDF；也可用“源码 / PDF”按钮切换。</p>
"""),
    ("报错怎么办", "check-error.png", "先选一条错误，看“说明与下一步”；可以定位，也可以展开原始日志。", r"""
<h2>先处理第一条错误</h2>
<p>编译没成功时，先看控制台中的“检查”或“错误”页。选中一条提示，点“定位问题”回到相关位置。
不确定原因时再展开“原始日志”，不用一次读完整份日志。</p>
<p>有“查看修复…”按钮时，先看准备修改的代码。只有点“应用修改”才会写入文稿，之后可以撤销。</p>
<h3>几个常见情况</h3>
<p><b>中文或字体报错</b>：中文模板使用 XeLaTeX。已有文稿可以从“编译”菜单选择 XeLaTeX 再试。<br>
<b>找不到图片</b>：检查文件名和相对路径；图片移走或改名后，引用也要相应修改。<br>
<b>命令不认识</b>：先检查拼写，再确认是否缺少相应宏包。</p>
<p>编译失败时，旧 PDF 可能还在，但它不是本次结果。修正后重新编译，看到最新状态再导出。</p>
"""),
    ("插图、引用和导出", "export-pdf.png", "图中是高级“准备提交”窗口；只导出一份 PDF 时不需要这些步骤。", r"""
<h2>把文件准备好，再发给别人</h2>
<p>普通文稿只需两步：点<b>“导出 PDF”</b>，选位置并点<b>“更新并导出”</b>。
有修改时自动保存并生成最新正式 PDF，完成后自动导出；没有新修改就不重复编译。
成功导出一次后，每次正式编译成功都会更新这个文件，重启后也记得；快速预览和失败编译不更新。
想换位置，再点“导出 PDF”；想保留固定版本，用“文件 → 停止自动更新导出 PDF”。
若目标文件被其他软件改过，程序会暂停这次更新并提示，不静默覆盖。</p>
<p>导出后，PDF 下方会常驻显示目标位置、上次导出时间和同步状态。
看到“待正式编译”就点一次正式编译；“更新失败”会一直保留，处理后再试。
这里也可以直接“打开位置”“换位置…”或“停止更新”。重开项目时先显示“待正式编译确认”，
不会只凭记住的位置就认定文件最新。</p>
<p>需要源码、检查报告或固定交付记录时，再用“文件 → 准备提交”，按提示审阅。
Block 项目也使用该流程。“未确认”不等于通过；生成的文件留在本机，不会自动上传。</p>
<h3>插图和引用放在哪里</h3>
<p>用左侧“项目导航”里的“插入”页选择图片。优先使用项目里的相对路径，例如 <code>figures/plot.png</code>，
其中文件名要换成你实际使用的图片。项目换到另一台电脑时，也要带上图片文件夹。</p>
<p>模板的引用库是 <code>bib/references.bib</code>。把文献条目放进去，再插入对应的引用键。
“检查引用”只检查本地内容，不会替你编造文献，也不会自动联网。</p>
<p>公式和表格编辑器里，先预览，再确认插入。取消会保留原文。常用模板可以从“项目导航”的“模板”页保存或导出，
下次写作时继续使用。</p>
"""),
)


def illustrated_page(body: str, filename: str, caption: str) -> str:
    image = asset_path(f"user-guide/{filename}")
    if image.is_file():
        url = escape(image.as_uri(), quote=True)
        picture = f'<p><a href="{url}"><img src="{url}" width="560" alt="{escape(caption)}"></a></p>'
        picture += f"<p><small>{escape(caption)} 点击图片可放大查看。</small></p>"
    else:
        picture = "<p><small>本机未找到图示，以上文字步骤仍可使用。</small></p>"
    return body + picture


class UserGuideDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新手导引")
        self.resize(820, 720)
        self.setMinimumSize(660, 460)
        self.example_root: Path | None = None
        layout = QVBoxLayout(self)
        title = QLabel("从改一个标题开始")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        ready = parent is not None and hasattr(parent, "app_settings")
        if ready:
            from app.gui.tutorial_controller import remembered_example
            self.example_root = remembered_example(parent)
        self.start_button = QPushButton("继续上次练习" if self.example_root else "开始练习（独立副本）")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setStyleSheet(PRIMARY_BUTTON_STATE_STYLE)
        self.start_button.setAutoDefault(False)
        self.start_button.setEnabled(ready)
        self.start_button.clicked.connect(self.accept)
        self.new_button = QPushButton("另建一个练习副本")
        self.new_button.setAutoDefault(False)
        self.new_button.setVisible(self.example_root is not None)
        self.new_button.clicked.connect(self._new_example)
        actions = ButtonFlowLayout()
        actions.addWidget(self.start_button)
        actions.addWidget(self.new_button)
        layout.addLayout(actions)
        self.pages = QTabWidget()
        self.pages.tabBar().setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._illustrations = {asset_path(f"user-guide/{item[1]}") for item in GUIDE_PAGES}
        scale = getattr(getattr(QApplication.instance(), "ui_scale_manager", None), "scale", 1.0)
        for name, image, caption, body in GUIDE_PAGES:
            browser = QTextBrowser()
            browser.setStyleSheet(f"font-size: {round(15 * scale)}px;")
            browser.setOpenLinks(False)
            browser.setOpenExternalLinks(False)
            browser.anchorClicked.connect(self._open_illustration)
            browser.setHtml(illustrated_page(body, image, caption))
            self.pages.addTab(browser, name)
        layout.addWidget(self.pages)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _new_example(self) -> None:
        self.example_root = None
        self.accept()

    def _open_illustration(self, url: QUrl) -> None:
        if url.isLocalFile() and Path(url.toLocalFile()) in self._illustrations:
            if not QDesktopServices.openUrl(url):
                QMessageBox.information(self, "图片没有打开", "系统没有打开图片。你仍可以在教程中查看这张图。")
