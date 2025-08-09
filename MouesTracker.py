from pynput import mouse, keyboard
import time
import math
import pandas as pd
from datetime import datetime
import os


class MouseTracker:
    """鼠标轨迹记录，并保存到'文件'或者'Excel'"""
    def __init__(self):
        # 初始化所有状态
        self.is_listening = False
        self.mouse_listener = None
        self.keyboard_listener = None
        self.excelWrite = False
        self.txtWrite = True
        self.reset_data()

        # 启动键盘监听
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press)
        self.keyboard_listener.start()
        print("按空格键开始/停止监听，Ctrl+C退出")

    def reset_data(self):
        """重置所有记录数据"""
        self.last_x = None  # 上一次x坐标
        self.last_y = None  # 上一次y坐标
        self.start_time = None  # 监听开始时间
        self.prev_time = None  # 前次记录时间
        self.data = []  # 存储的数据

    def on_move(self, x, y):
        """处理鼠标移动事件"""
        current_time = time.time()

        # 初始化处理
        if None in (self.last_x, self.last_y, self.start_time):
            self.last_x, self.last_y = x, y
            self.start_time = current_time
            self.prev_time = current_time
            return

        # 计算移动参数
        dx = x - self.last_x
        dy = y - self.last_y
        distance = math.hypot(dx, dy)
        time_diff = (current_time - self.prev_time) * 1000  # 毫秒
        elapsed_time = (current_time - self.start_time) * 1000

        # 计算速度
        velocity = distance / time_diff if time_diff > 0 else 0.0

        # 存储数据
        self.data.append([
            x,  # 当前绝对x坐标
            y,  # 当前绝对y坐标
            round(elapsed_time, 1),  # 时间戳（ms）
            round(velocity, 4)  # 速度（px/ms）
        ])

        # 更新记录
        self.last_x, self.last_y = x, y
        self.prev_time = current_time

    def toggle_listening(self):
        """切换监听状态"""
        if not self.is_listening:
            self.start_listening()
        else:
            self.stop_listening()

    def start_listening(self):
        """开始监听"""
        if not self.is_listening:
            self.reset_data()
            self.mouse_listener = mouse.Listener(on_move=self.on_move)
            self.mouse_listener.start()
            self.is_listening = True
            print("\n监听已启动...")

    def stop_listening(self):
        """停止监听"""
        if self.is_listening and self.mouse_listener:
            self.mouse_listener.stop()
            self.is_listening = False
            print("\n监听已停止")
            if self.excelWrite:
                self.save_to_excel()
                print("已收集数据条数:", len(self.data))
            if self.txtWrite:
                self.process_and_save_data()
                print("已收集数据条数:", len(self.data))


    def on_key_press(self, key):
        """键盘事件处理"""
        try:
            if key == keyboard.Key.space:
                self.toggle_listening()
        except AttributeError:
            pass

    def save_to_excel(self, filename=None):
        """保存数据到Excel"""
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H_%M_%S")
                #filename = f"files/mouse_data_{timestamp}.xlsx"
                filename = f"files/{self.data[-1][0]-self.data[0][0]}.xlsx"

            df = pd.DataFrame(
                self.data,
                columns=["X坐标", "Y坐标", "时间(ms)", "速度(px/ms)"]
            )

            df.to_excel(
                excel_writer=filename,
                sheet_name='轨迹数据',
                index=False,
                engine='openpyxl'
            )
            print(f"数据已保存到 {filename}")
            return True
        except PermissionError:
            print(f"错误：文件 {filename} 被占用")
            return False
        except Exception as e:
            print(f"保存失败: {str(e)}")
            return False

    def process_and_save_data(self):
        """
        将读取的数据写入.TXT
        生成的是相对坐标
        :return:
        """
        try:
            # 1. 检查数据合法性
            if not self.data or len(self.data[0]) < 3:  # type: ignore
                raise ValueError("数据格式不符合要求")

            # 2. 获取基准值
            base = [self.data[0][0], self.data[0][1], self.data[0][2]]  # type: ignore

            # 3. 创建目标目录
            #os.makedirs("files", exist_ok=True)

            # 4. 生成文件名（注意转换为数值类型）
            filename = f"files/{int(self.data[-1][0]) - int(base[0])}.txt"  # type: ignore

            # 5. 处理数据并写入文件
            with open(filename, "w", encoding="utf-8") as f:
                # 新增标题行（注意使用制表符对齐）
                f.write("#X轴\tY轴\t时间\n")
                for item in self.data:
                    # 确保每个子列表至少有3个元素
                    if len(item) < 3:
                        continue  # 跳过不合法数据

                    # 转换为数值类型并计算差值
                    try:
                        processed = [
                            float(item[0]) - float(base[0]),  # type: ignore
                            float(item[1]) - float(base[1]),  # type: ignore
                            float(item[2]) - float(base[2])  # type: ignore
                        ]
                    except (ValueError, TypeError):
                        continue  # 跳过无法转换的数据

                    # 写入前三个处理后的值
                    f.write(f"{processed[0]}    {processed[1]}    {processed[2]}\n")
                print(f"文件已保存至 {filename}")
            return f"文件已保存至 {filename}"

        except Exception as e:
            return f"处理失败: {str(e)}"

    def run(self):
        """保持程序运行"""
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            if self.mouse_listener:
                self.mouse_listener.stop()
            if self.keyboard_listener:
                self.keyboard_listener.stop()
            print("\n程序已退出")


if __name__ == "__main__":
    tracker = MouseTracker()
    tracker.run()