import re
class instruction:
    # 定义模式与处理函数的映射关系
    def __init__(self,):
        self.PATTERN_HANDLERS = [
            (r'所有指令|指令', self.handle_all_commands),
            (r'开始获取|开始', self.handle_start_fetch),  # 支持多个关键词
            (r'停止|终止|暂停', self.handle_stop),  # 使用匿名函数
        ]
        self.ALLZhiLing = [
            ['所有指令|指令:获取所有指令',
             '开始获取|开始:开始执行程序',
             '停止|终止|暂停:关闭执行程序']
        ]
    def handle_all_commands(self,):
        """处理所有指令的逻辑"""
        print("检测到指令查询，正在列出所有可用指令...")
        # 这里添加实际业务逻辑
        from WindowAutomator import WindowAutomator
        WindowAutomator().send_message(message=self.ALLZhiLing)
        return "ALLCommand"

    def handle_start_fetch(self,):
        """处理获取的指令"""
        print("启动数据获取流程...")
        from WindowAutomator import WindowAutomator
        WindowAutomator().send_message(message="已经开始运行程序")
        # 这里添加实际业务逻辑
        return "RUN"

    def handle_stop(self,):
        """处理暂停的指令"""
        from WindowAutomator import WindowAutomator
        WindowAutomator().send_message(message="已经停止运行程序")
        return "STOP"

    def main(self,content):
        """内容处理器主函数"""
        for pattern, handler in self.PATTERN_HANDLERS:
            if re.search(pattern, content, flags=re.IGNORECASE):
                print(f"匹配到模式：{pattern}")
                return handler()
        return None