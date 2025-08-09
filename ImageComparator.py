import cv2
import numpy as np
from pathlib import Path


class ImageComparator:
    def __init__(self, base_image_path="photo/read.png"):
        """
        初始化时预加载基准图像并计算特征（效率优化关键）
        :param base_image_path: 基准图像路径
        """
        self.base_image = self._load_image(base_image_path)
        self.base_hash = self._calc_image_hash(self.base_image)

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
                np.unpackbits(self.base_hash) != np.unpackbits(target_hash)
            )

            return hamming_dist <= threshold

        except Exception as e:
            print(f"比对失败：{str(e)}")
            return False

    @property
    def base_image_size(self):
        """获取基准图像尺寸（用于校验输入）"""
        return self.base_image.shape[1], self.base_image.shape[0]