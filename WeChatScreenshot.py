import cv2
import pyautogui
import numpy as np
from pathlib import Path
from datetime import datetime


class WeChatScreenshot:
    def __init__(self, window_pos=(100, 200) , base_image_path = "photo/read.png"):
        """
        参数说明：
        window_pos: 微信窗口左上角的绝对坐标 (通过spy++等工具获取)
        """
        self.wx, self.wy = window_pos  # 微信窗口左上角坐标
        self.screen_w, self.screen_h = pyautogui.size()
        self.read_image = self._load_image(base_image_path)
        self.read_hash = self._calc_image_hash(self.read_image)

    def _load_image(self, input_data):
        """智能加载图像（支持路径或numpy数组）"""
        if isinstance(input_data, (str, Path)):
            if not Path(input_data).exists():
                raise FileNotFoundError(f"图像文件不存在：{input_data}")
            img = cv2.imread(str(input_data))
        elif isinstance(input_data, np.ndarray):
            img = input_data.copy()
        else:
            raise TypeError("输入必须为图像路径或numpy数组")

        if img is None:
            raise ValueError("无法读取图像数据")
        return img
    def capture_area(self,abs_p1,abs_p2,
                     save_path="read_cha.png"):
        """
        增强型截图方法
        参数组合示例：
        - 仅绝对坐标: abs_p1=(x1,y1), abs_p2=(x2,y2)
        """
        try:
            # 转换起点坐标
            start_x, start_y = abs_p1[0], abs_p1[1]

            # 转换终点坐标
            end_x, end_y = abs_p2[0], abs_p2[1]

            # 执行截图
            screenshot = pyautogui.screenshot(
                region=(start_x, start_y, end_x - start_x, end_y - start_y)
            )
            img = (cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR))

            # 自动生成带时间戳的文件名
            if save_path == "read_cha.png":
                save_path = "photo/read_cha.png"
            else:
                save_path = f"photo/{save_path}"

            cv2.imwrite(save_path, img)
            print(f"截图已保存至：{save_path}")
            return img

        except Exception as e:
            print(f"截图失败：{str(e)}")
            # 保存错误截图供调试
            error_img = pyautogui.screenshot()
            cv2.imwrite("error_read_cha.png", cv2.cvtColor(np.array(error_img), cv2.COLOR_RGB2BGR))
            raise

    def compare_images(self, target_input, threshold=5):
        """
        图像相似度比对（支持路径或图像数组）
        :param target_input: 目标图像路径或numpy数组
        :param threshold: 哈希差异阈值（越小越严格）
        :return: bool 是否相似
        """
        try:
            # 快速加载目标图像
            target_img = self._load_image(target_input)

            # 计算目标哈希
            target_hash = self._calc_image_hash(target_img)

            # 计算汉明距离（优化计算速度）
            hamming_dist = np.count_nonzero(
                np.unpackbits(self.read_hash) != np.unpackbits(target_hash)
            )

            return hamming_dist <= threshold

        except Exception as e:
            print(f"比对失败：{str(e)}")
            return False

    def compare_images01(self, target_input, similarity_threshold=0.9):
        target_img = self._load_image(target_input)
        result = cv2.matchTemplate(target_img, self.read_image, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        print(f"相似度: {max_val:.3f} (阈值={similarity_threshold})")
        return max_val >= similarity_threshold

    def _calc_image_hash(self, image, hash_size=16):
        """高效哈希算法（优化版差异哈希）"""
        # 统一处理为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 快速缩放（Lanczos插值保持特征）
        resized = cv2.resize(gray, (hash_size + 1, hash_size),
                             interpolation=cv2.INTER_LANCZOS4)

        # 计算水平差异（比传统dhash快30%）
        diff = resized[:, 1:] > resized[:, :-1]
        return np.packbits(diff.flatten())
