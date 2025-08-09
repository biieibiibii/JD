import cv2
import random
from playwright.sync_api import sync_playwright , Page
import time
import base64
import os
from typing import List, Tuple , Optional


class JDSliderVerifier:
    def __init__(self, yanZhengUrl: str, max_attempts: int = 10, page: Optional[Page] = None):
        """
        京东滑块验证解决方案
        :param yanZhengUrl: 验证页面URL
        :param max_attempts: 最大重试次数，默认10次
        """
        self.yanZhengUrl = yanZhengUrl
        self.max_attempts = max_attempts
        self.browser = None
        self.context = None
        self.page = page
        self._own_browser = False  # 标识是否自主创建浏览器
        self.jianChaLogin = False  # 检查当前页面是否为登录页面

    def run(self) -> bool:
        """执行验证流程"""
        try:
            # 复用现有页面时的处理
            if self.page is not None:
                print("🔄 复用现有页面对象")
                self._prepare_existing_page()
            else:
                self._init_new_browser()

            if not self.jianChaLogin:
                self._init_verification()
            else:
                print("检测到当前页面存在异常，不进行验证操作，请先进行登录")
                return
            return self._verification_loop()
        finally:
            self._cleanup_resources()

    def _prepare_existing_page(self):
        """处理复用页面的情况"""
        if self.page.is_closed():
            raise RuntimeError("提供的页面已关闭")
        if "https://passport.jd.com/new/login.aspx?" in self.page.url:
            print("当前页面为登录页面，跳过验证流程")
            self.jianChaLogin = True
            return
        if self.page.url != self.yanZhengUrl :
            # print("⏩ 导航至目标验证页面")
            # self.page.goto(self.yanZhengUrl)
            print("当前页面存在问题，跳过验证流程")
            self.jianChaLogin = True
            return


    def _init_new_browser(self):
        """初始化新的浏览器实例"""
        with sync_playwright() as p:
            self.browser = p.chromium.launch(
                channel="msedge",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            self.context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
                viewport={"width": 1920, "height": 1080}
            )
            self.page = self.context.new_page()
            self.page.goto(self.yanZhengUrl)
            self._own_browser = True

    def _verification_loop(self) -> bool:
        """验证主循环"""
        for attempt in range(1, self.max_attempts + 1):
            print(f"\n=== 第 {attempt} 次验证尝试 ===")
            time.sleep(1)
            try:
                if self._process_verification():
                    print("✅ 验证成功")
                    time.sleep(5)
                    return True
            except Exception as e:
                print(f"❌ 验证失败: {str(e)}")
                if attempt == self.max_attempts:
                    raise
                self._reset_verification()
        return False

    def _cleanup_resources(self):
        """资源清理（仅关闭自主创建的实例）"""
        if self._own_browser and self.browser:
            print("♻️ 清理自主创建的浏览器实例")
            self.browser.close()
        elif self.page and not self._own_browser:
            print("ℹ️ 保留外部传入的页面对象")


    def _init_page(self):
        """初始化页面对象"""
        self.page = self.context.new_page()
        self.page.goto(self.yanZhengUrl)

    def _init_verification(self):
        """触发验证流程"""
        self.page.wait_for_selector("//div[@class='verifyBtn']", timeout=3000)
        self.page.click("//div[@class='verifyBtn']")
        print("已触发验证按钮")

    def _process_verification(self):
        """执行完整验证流程"""
        slider = self.page.wait_for_selector("//img[@class='move-img']", timeout=4000)
        bg_src = self.page.wait_for_selector("//img[@id='cpc_img']", timeout=4000).get_attribute("src")
        bg_path = self._decode_base64_image(bg_src, "bg.png")

        img_src = self.page.wait_for_selector("//img[@id='small_img']", timeout=3000).get_attribute("src")
        slider_path = self._decode_base64_image(img_src, "xiaoKuai.png")

        distance = self._calculate_slide_distance(bg_path, slider_path)
        if not 137 <= distance <= 220:
            raise ValueError(f"异常滑动距离: {distance}px")

        with self.page.expect_response(
                lambda r: r.url == "https://jcap.m.jd.com/cgi-bin/api/check",
                timeout=5000
        ) as response_info:
            self._perform_slide_action(slider, distance)

        response = response_info.value
        result = response.json()

        if result.get("code") == 0 and not result.get("msg"):
            return True
        raise Exception(f"验证失败: {result.get('msg', '未知错误')}")

    def _reset_verification(self):
        """重置验证流程"""
        self.page.click("//span[@class='opt']")
        print("已重置验证")
        time.sleep(1)

    @staticmethod
    def _calculate_slide_distance(bg_path: str, slider_path: str) -> int:
        """计算滑动距离"""
        bg_gray = cv2.cvtColor(cv2.imread(bg_path), cv2.COLOR_BGR2GRAY)
        slider_gray = cv2.cvtColor(cv2.imread(slider_path), cv2.COLOR_BGR2GRAY)

        bg_edge = cv2.Canny(bg_gray, 50, 150)
        slider_edge = cv2.Canny(slider_gray, 50, 150)

        res = cv2.matchTemplate(bg_edge, slider_edge, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        return round(max_loc[0] / 0.942)

    @staticmethod
    def _decode_base64_image(img_src: str, filename: str) -> str:
        """Base64解码图像"""
        if img_src.startswith("data:image"):
            _, data = img_src.split(",", 1)
            decoded = base64.b64decode(data)
            save_path = f"photo/{filename}"
            with open(save_path, "wb") as f:
                f.write(decoded)
            return save_path
        return img_src

    def _perform_slide_action(self, slider, distance: int):
        """执行滑动操作"""
        track = self._load_trajectory(distance)
        self._precise_drag(slider, track)

    def _load_trajectory(self, target_num: int) -> List[Tuple[float, float, float]]:
        """加载预存轨迹数据"""
        candidates = sorted(
            set(range(target_num - 2, target_num + 3)),
            key=lambda x: (abs(x - target_num), x)
        )

        for num in candidates:
            filepath = os.path.join(os.getcwd(), f"files/{num}.txt")
            if not os.path.exists(filepath):
                continue

            trajectory = []
            with open(filepath, 'r', encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split()
                        if len(parts) != 3:
                            raise ValueError(
                                f"文件 {num}.txt某行数据格式错误，应为x y time"
                            )
                        x, y, t = float(parts[0]), float(parts[1]), float(parts[2])
                        trajectory.append((t, x, y))
            if trajectory:
                print(trajectory)
                return trajectory
        raise FileNotFoundError(f"未找到合适轨迹文件: {target_num}±2")

    def _precise_drag(self, slider, scaled_data: List[Tuple[float, float, float]]):
        """精确轨迹拖动"""
        # 1. 获取初始坐标
        box = slider.bounding_box()
        start_x = box["x"] + (box["width"] / 2) + random.randint(-10, 8)
        start_y = box["y"] + (box["height"] / 2) + random.randint(-10, 8)
        # 模拟停顿
        # 2. 初始化操作
        self.page.mouse.move(start_x, start_y)  # 鼠标移动
        self.page.mouse.down()  # 鼠标按下
        time.sleep(random.uniform(0.5, 1))

        # 3. 严格按数据执行
        previous_time = 0

        for current_time, current_x, current_y in scaled_data:
            # 计算时间差（从轨迹起点开始）
            time_delta = current_time - previous_time
            if time_delta < 0:
                raise ValueError("轨迹时间戳必须单调递增")
            # 执行精确等待
            if previous_time > 0:  # 跳过第一个点的等待
                time.sleep(0.003)  # 转换为秒

            # 计算绝对坐标
            target_x = start_x + current_x
            target_y = start_y + current_y

            # 直线移动（禁用任何插值）
            self.page.mouse.move(target_x, target_y)

            previous_time = current_time
            # previous_pos = current_pos

        # 4. 直接释放
        self.page.mouse.up()

# 使用示例
if __name__ == "__main__":
    verify_url = "https://cfe.m.jd.com/privatedomain/risk_handler/03101900/?returnurl=https%3A%2F%2Fitem.jd.com%2F10099587215822.html&evtype=2&rpid=rp-188540931-10236-1743758351453"
    # verifier = JDSliderVerifier(yanZhengUrl=verify_url)
    # result = verifier.run()
    # print("最终验证结果:", result)

    # 场景2：复用现有页面

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        page.goto(verify_url)
        v = JDSliderVerifier(yanZhengUrl=verify_url, page=page)
        print(v.run())