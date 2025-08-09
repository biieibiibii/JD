import pyautogui            #操作鼠标，键盘等自动化库
import pygetwindow as gw    #获取当前窗口信息
import keyboard             #监听键盘事件
import time
import pyperclip            #将内容复制到粘贴板
from WeChatScreenshot import WeChatScreenshot
from queue import Queue
import threading

class Controller:
    def __init__(self):
        self.command_queue = Queue()  # 线程安全的指令队列
        self.running = threading.Event()  # 运行状态标志
        self.stop_requested = threading.Event()  # 停止请求标志

class WindowAutomator:
    """窗口自动化操作类，支持窗口管理、坐标记录、消息发送等功能
    """

    def __init__(self, window_title="微信", default_left=100, default_top=200, default_width=800, default_height=600):
        """
        初始化自动化实例
        :param window_title: 目标窗口标题
        :param default_left: 默认窗口左坐标
        :param default_top: 默认窗口顶坐标
        :param default_width: 默认窗口宽度
        :param default_height: 默认窗口高度
        """
        self.window_title = window_title
        self.default_left = default_left
        self.default_top = default_top
        self.default_headCoor = [
            [491,587],
            [529,627],
            [391,387],
            [429,427]
        ]#前两个为头像的绝对坐标的左上角和右下角，后两个为相对坐标的左上角和右下角
        self.default_messageCoor = [[554,604],[454,404]]#复制按钮
        self.first = [[164,113]]#第一消息
        self.default_size = (default_width, default_height)
        self.target_window = self._safe_get_window()
        self.records = []
        self.WeChat = WeChatScreenshot()
        self.controller = Controller()


    def list_all_windows(self):
        """列出所有窗口信息"""
        for win in gw.getAllWindows():
            print(f"窗口: {win.title} | 位置: ({win.left}, {win.top}) | 尺寸: {win.width}x{win.height}")

    def _safe_get_window(self):
        """安全获取窗口对象"""
        windows = gw.getWindowsWithTitle(self.window_title)
        if not windows:
            raise Exception(f"未找到标题包含'{self.window_title}'的窗口")
        return windows[0]

    def adjust_window(self):
        """调整窗口到预设位置和大小"""
        try:
            # self.target_window = self._safe_get_window()

            if self.target_window.isMinimized:
                self.target_window.restore()

            self.target_window.moveTo(self.default_left, self.default_top)
            self.target_window.resizeTo(*self.default_size)

            # print(f"窗口位置已调整 -> X:{self.default_left} Y:{self.default_top}")
            # print(f"窗口尺寸已调整 -> {self.default_size[0]}x{self.default_size[1]}")

        except Exception as e:
            print(f"窗口调整失败: {str(e)}")
            raise

    def track_coordinates(self):
        """实时坐标追踪功能"""
        print("\n坐标追踪模式启动")
        print("空格键 - 记录坐标 | ESC键 - 退出")

        self.records.clear()
        try:
            while True:
                # 动态获取最新窗口位置
                try:
                    win = self._safe_get_window()
                    win_left, win_top = win.left, win.top
                except:
                    win_left = win_top = None

                # 获取坐标信息
                abs_x, abs_y = pyautogui.position()
                rel_x = abs_x - win_left if win_left else None
                rel_y = abs_y - win_top if win_top else None

                # 实时显示信息
                info = f"绝对坐标: ({abs_x:4d}, {abs_y:4d})"
                if rel_x is not None:
                    info += f" | 相对坐标: ({rel_x:4d}, {rel_y:4d})"
                print(info, end='\r')

                # 按键处理
                if keyboard.is_pressed('space'):
                    record = {
                        'absolute': (abs_x, abs_y),
                        'relative': (rel_x, rel_y) if None not in [rel_x, rel_y] else None
                    }
                    self.records.append(record)
                    print(f"\n记录坐标: {record}")
                    time.sleep(0.3)

                if keyboard.is_pressed('esc'):
                    print("\n退出追踪模式")
                    break

                time.sleep(0.05)

        except Exception as e:
            print(f"追踪异常: {str(e)}")

        return self.records

    def _convert_coords(self, abs_coord=None, rel_coord=None):
        """
        智能坐标转换与验证系统
        :param abs_coord: 绝对坐标 (x, y)
        :param rel_coord: 相对坐标 (x, y)
        :return: 验证后的绝对坐标
        """
        # 输入校验
        if abs_coord is None and rel_coord is None:
            raise ValueError("必须提供至少一种坐标（绝对或相对）")

        # 计算理论绝对坐标
        if rel_coord is not None:
            calc_abs = (
                self.default_left + rel_coord[0],
                self.default_top + rel_coord[1]
            )
        else:
            calc_abs = abs_coord

        # 双重坐标校验
        if abs_coord is not None and rel_coord is not None:
            deviation = (
                abs(abs_coord[0] - calc_abs[0]),
                abs(abs_coord[1] - calc_abs[1])
            )
            if deviation[0] > 5 or deviation[1] > 5:
                print(f"坐标校验异常！理论绝对坐标{calc_abs} vs 实际绝对坐标{abs_coord}")
                return abs_coord  # 优先使用用户提供的绝对坐标
        return calc_abs

    def _chuLi(self):
        """
        截图头像，判断是否能进行复制信息
        绝对坐标: ( 491,  587) | 相对坐标: ( 391,  387)
        绝对坐标: ( 529,  627) | 相对坐标: ( 429,  427)
        消息位置
        绝对坐标: ( 554,  604) | 相对坐标: ( 454,  404)
        :return:
        """
        command = self._getCommand()
        if command is None:
            return
        self.controller.command_queue.put(command)
        # 解析执行指令
        if command == "RUN":
            print("启动任务")
            self.controller.stop_requested.clear()
            if not self.controller.running.is_set():
                # 创建新线程来执行任务（避免阻塞主调度）
                worker = threading.Thread(target=self.handle_start_fetch)
                worker.start()  # 启动线程
        elif command == "STOP":
            print("暂停任务")
            self.controller.stop_requested.set()


    def handle_start_fetch(self):
        from JDScraper import JDScraper
        """启动执行器（在工作线程中执行）"""
        print("创建爬取任务...")
        self.controller.running.set()  # 标记为运行状态
        with JDScraper(controller=self.controller,headless=False) as scraper:
            scraper.run()
        print("爬取任务完成")
        self.controller.running.clear()  # 清除运行状态
    def _getCommand(self):
        from instruction import instruction
        #调整窗口大小到合适位置
        self.adjust_window()
        if self.target_window.isMinimized:
            self.target_window.restore()
        #点击第一条信息164.113
        self._clickFirstChat()
        #判断截图所需头像坐标是否符合预期
        head1 = self._convert_coords(self.default_headCoor[0], self.default_headCoor[2])
        head2 = self._convert_coords(self.default_headCoor[1], self.default_headCoor[3])
        imp = self.WeChat.capture_area(abs_p1=head1, abs_p2=head2)
        a = self.WeChat.compare_images01(imp)
        print(a)
        if a:
            content = self.copy()
            # 最小化窗口，为下一次打开做铺垫
            self._clickMinimize()
            return instruction().main(content)

        self._clickMinimize()
        return None

    def _clickFirstChat(self, abs=[164, 113]):
        """
        点击第一条聊天信息
        :param abs: 相对坐标
        :return:
        """
        # 点击第一条信息164.113
        abs_chat = (
            self.target_window.left + abs[0],
            self.target_window.top + abs[1]
        )
        pyautogui.click(*abs_chat)
        time.sleep(1)

    def _clickMinimize(self, abs=[771, 15]):
        """
        点击窗口最小化
        :param abs: 相对坐标
        :return:
        """
        # 点击第一条信息164.113
        abs_chat = (
            self.target_window.left + abs[0],
            self.target_window.top +  abs[1]
        )
        pyautogui.click(*abs_chat)
        time.sleep(1)

    def copy(self,message_coor=[454,404]):
        """
        :param message_coor:消息的坐标
        :return:
        """
        message_coor = self._convert_coords(rel_coord=message_coor)
        #鼠标移动到消息框并右击
        time.sleep(0.1)
        pyautogui.click(*message_coor,button='right')
        #鼠标移动到复制按钮
        fuZhi = {
            message_coor[0]+40,
            message_coor[1]+30
        }
        pyautogui.click(*fuZhi)
        #获取复制消息，并保存到变量中
        time.sleep(0.5)  # 等待复制完成
        content = pyperclip.paste()
        return content

    def send_message(self, rel_chat_pos=[164,113], rel_send_pos=[763,590] , message="自动化消息测试", retry=3):
        """自动化消息发送"""
        for attempt in range(retry):
            try:
                # self.target_window = self._safe_get_window()
                if self.target_window.isMinimized:
                    self.target_window.restore()

                # 计算绝对坐标
                abs_chat = (
                    self.target_window.left + rel_chat_pos[0],
                    self.target_window.top + rel_chat_pos[1]
                )
                abs_send = (
                    self.target_window.left + rel_send_pos[0],
                    self.target_window.top + rel_send_pos[1]
                )

                # 执行操作流程
                self.target_window.activate()
                time.sleep(0.5)

                pyautogui.click(*abs_chat)
                time.sleep(1)

                pyperclip.copy(message)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.5)

                pyautogui.click(*abs_send)
                print("消息发送成功")
                self._clickMinimize()
                return True

            except Exception as e:
                print(f"尝试 {attempt + 1} 失败: {str(e)}")
                time.sleep(1)
                return False

        print("消息发送失败")
        return False

if __name__ == '__main__':
    # 使用示例
    wechat_bot = WindowAutomator(
        window_title="微信",
        default_left=100,
        default_top=200,
        default_width=800,
        default_height=600
    )

    # 调整窗口位置
    # wechat_bot.adjust_window()
    #
    # #记录坐标（可选）
    # records = wechat_bot.track_coordinates()
    # print("记录到的坐标：", records)
    # wechat_bot._chuLi()
    # #发送消息
    # wechat_bot.send_message(
    #     rel_chat_pos=(164, 113),
    #     rel_send_pos=(763, 590),
    #     message="自动化测试消息"
    # )
    try:
        # 模拟每隔60秒自动执行一次调度检查
        while True:
            wechat_bot._chuLi()  # 执行调度检查
            print("\n等待下一次调度...")
            time.sleep(60)  # 暂停20秒
    except KeyboardInterrupt:
        print("\n程序被手动终止")