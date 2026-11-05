"""资金数据清洗工具 - 主GUI程序"""
import os
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLineEdit, QPushButton, QFileDialog, QCheckBox,
    QProgressBar, QLabel, QStatusBar, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QFont, QColor, QPainter, QPixmap
from core.pipeline import Pipeline


def get_default_output():
    """获取默认输出目录（桌面）"""
    if os.name == 'nt':
        return os.path.join(os.environ.get('USERPROFILE', 'C:\\'), 'Desktop')
    else:
        return os.path.join(os.environ.get('HOME', '/'), 'Desktop')


def _find_icon_path():
    """在 PyInstaller 打包、源码运行等不同环境下定位程序图标。"""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "resources", "icon.ico"))
    candidates.append(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "icon.ico")
    )
    if getattr(sys, "frozen", False):
        candidates.append(
            os.path.join(os.path.dirname(sys.executable), "resources", "icon.ico")
        )
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _load_app_icon() -> QIcon:
    """加载程序图标；文件缺失或加载失败时生成兜底图标，避免窗口/任务栏无图标。"""
    icon_path = _find_icon_path()
    if icon_path:
        icon = QIcon(icon_path)
        if not icon.isNull():
            return icon

    # 兜底：程序化绘制"TC"图标（蓝底圆角 + 白色 TC，与 icon.ico 风格一致）
    size = 256
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#2F6BFF"))
    painter.drawRoundedRect(pixmap.rect(), size * 0.22, size * 0.22)
    painter.setPen(QColor("white"))
    font = QFont("Arial Black" if os.name == "nt" else "Helvetica Neue", int(size * 0.32))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "TC")
    painter.end()
    return QIcon(pixmap)


class PipelineWorker(QThread):
    """在子线程中运行 Pipeline，避免阻塞 GUI"""
    progress_signal = Signal(str, float, str)
    finished_signal = Signal(bool, str)
    error_signal = Signal(str)

    def __init__(self, input_zips, output_dir, keep_temp, stop_on_error):
        super().__init__()
        self.input_zips = input_zips
        self.output_dir = output_dir
        self.keep_temp = keep_temp
        self.stop_on_error = stop_on_error

    def run(self):
        pipeline = Pipeline(
            self.input_zips,
            self.output_dir,
            self.keep_temp,
            self.stop_on_error
        )

        original_report = pipeline._report

        def qt_report(detail, percentage, step_name=""):
            original_report(detail, percentage, step_name)
            self.progress_signal.emit(step_name, percentage, detail)

        pipeline._report = qt_report

        try:
            success = pipeline.run()
            self.finished_signal.emit(success, "处理完成" if success else "处理被取消")
        except Exception as e:
            import traceback
            self.error_signal.emit(f"{e}\n{traceback.format_exc()}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_files: list[str] = []
        self.worker: PipelineWorker | None = None
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("资金数据清洗工具")
        self.setMinimumSize(700, 500)
        self.resize(800, 600)

        self.setWindowIcon(_load_app_icon())

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # === 输入文件组 ===
        input_group = QGroupBox("输入文件")
        input_layout = QVBoxLayout(input_group)

        file_select_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("请选择ZIP文件（支持多选）...")
        file_select_layout.addWidget(self.file_path_edit)

        self.select_btn = QPushButton("选择ZIP文件")
        self.select_btn.clicked.connect(self._select_files)
        file_select_layout.addWidget(self.select_btn)
        input_layout.addLayout(file_select_layout)

        self.file_count_label = QLabel("未选择文件")
        self.file_count_label.setStyleSheet("color: gray;")
        input_layout.addWidget(self.file_count_label)

        main_layout.addWidget(input_group)

        # === 输出目录组 ===
        output_group = QGroupBox("输出目录")
        output_layout = QHBoxLayout(output_group)

        self.output_path_edit = QLineEdit(get_default_output())
        output_layout.addWidget(self.output_path_edit)

        self.output_btn = QPushButton("选择文件夹")
        self.output_btn.clicked.connect(self._select_output_dir)
        output_layout.addWidget(self.output_btn)

        main_layout.addWidget(output_group)

        # === 选项组 ===
        option_group = QGroupBox("选项")
        option_layout = QHBoxLayout(option_group)

        self.keep_temp_cb = QCheckBox("保留中间文件")
        self.keep_temp_cb.setChecked(False)
        option_layout.addWidget(self.keep_temp_cb)

        self.stop_on_error_cb = QCheckBox("遇错停止")
        self.stop_on_error_cb.setChecked(True)
        option_layout.addWidget(self.stop_on_error_cb)

        option_layout.addStretch()
        main_layout.addWidget(option_group)

        # === 运行按钮 ===
        run_layout = QHBoxLayout()
        run_layout.addStretch()

        self.run_btn = QPushButton("▶ 开始处理")
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setMinimumWidth(160)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #2962FF;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #0039CB;
            }
            QPushButton:disabled {
                background-color: #B0BEC5;
            }
        """)
        self.run_btn.clicked.connect(self._start_processing)
        run_layout.addWidget(self.run_btn)
        run_layout.addStretch()
        main_layout.addLayout(run_layout)

        # === 进度组 ===
        progress_group = QGroupBox("进度")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_detail_label = QLabel("就绪")
        progress_layout.addWidget(self.progress_detail_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.step_label = QLabel("")
        self.step_label.setStyleSheet("color: #546E7A;")
        progress_layout.addWidget(self.step_label)

        main_layout.addWidget(progress_group)

        # === 版本信息 ===
        version_label = QLabel("V1.9")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #90A4AE; font-size: 14px; font-weight: bold;")
        main_layout.addWidget(version_label)

        # === 状态栏 ===
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        copyright_label = QLabel("济宁经侦-田成 57018 © 2026")
        copyright_label.setStyleSheet("color: #78909C; padding-right: 10px;")
        self.status_bar.addPermanentWidget(copyright_label)

    def _select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择ZIP文件",
            "",
            "ZIP文件 (*.zip);;所有文件 (*.*)"
        )
        if files:
            self.selected_files = files
            self.file_path_edit.setText("; ".join(files))
            self.file_count_label.setText(f"已选择: {len(files)} 个文件")
            self.file_count_label.setStyleSheet("color: #2E7D32;")

    def _select_output_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            self.output_path_edit.text()
        )
        if directory:
            self.output_path_edit.setText(directory)

    def _start_processing(self):
        if not self.selected_files:
            QMessageBox.warning(self, "提示", "请先选择ZIP文件")
            return

        output_dir = self.output_path_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "提示", "请选择输出目录")
            return

        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法创建输出目录: {e}")
                return

        self._set_controls_enabled(False)
        self.progress_bar.setValue(0)
        self.step_label.setText("")

        self.worker = PipelineWorker(
            self.selected_files,
            output_dir,
            self.keep_temp_cb.isChecked(),
            self.stop_on_error_cb.isChecked()
        )
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.error_signal.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, step_name: str, percentage: float, detail: str):
        self.step_label.setText(step_name)
        self.progress_detail_label.setText(detail)
        if percentage >= 0:
            self.progress_bar.setValue(int(percentage))
        self.status_bar.showMessage(detail)

    def _on_finished(self, success: bool, message: str):
        self._set_controls_enabled(True)
        if success:
            self.progress_bar.setValue(100)
            self.status_bar.showMessage("处理完成")
            QMessageBox.information(
                self, "完成",
                f"处理完成！\n输出目录: {self.output_path_edit.text()}\n"
                f"详细日志请查看 error.log"
            )
        else:
            self.status_bar.showMessage("处理被取消")

    def _on_error(self, error_msg: str):
        self._set_controls_enabled(True)
        self.status_bar.showMessage("处理出错")
        QMessageBox.critical(
            self, "处理错误",
            f"处理过程中发生错误:\n\n{error_msg}\n\n"
            f"详细信息已写入 error.log"
        )

    def _set_controls_enabled(self, enabled: bool):
        self.select_btn.setEnabled(enabled)
        self.output_btn.setEnabled(enabled)
        self.run_btn.setEnabled(enabled)
        self.keep_temp_cb.setEnabled(enabled)
        self.stop_on_error_cb.setEnabled(enabled)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(_load_app_icon())

    font = QFont("Microsoft YaHei" if os.name == "nt" else "PingFang SC", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
