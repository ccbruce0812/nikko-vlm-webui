import sys
import os

# 確保專案根目錄在系統路徑中，以解決模組匯入問題 (ImportError)
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.ui.main_window import MainWindow

def main():
    # 針對高解析度螢幕進行縮放優化
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    # 建立應用程式實例
    app = QApplication(sys.argv)
    
    # 使用 Fusion 風格確保跨平台 (Linux/Windows) 的一致觀感
    app.setStyle("Fusion")
    
    try:
        # 初始化並顯示主視窗 (將連帶初始化控制面板與獨立的影像畫布)
        window = MainWindow()
        window.show()
        
        # 進入主迴圈
        sys.exit(app.exec())
    except Exception as e:
        print(f"Startup Critical Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()