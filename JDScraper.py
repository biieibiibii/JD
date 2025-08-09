import os
import json
import time
import random
import traceback
from typing import List,Dict,Tuple
from playwright.sync_api import sync_playwright

from StAi.项目.拍立得相纸到货抓取.JDSliderVerifier import JDSliderVerifier
from StAi.项目.拍立得相纸到货抓取.JDgetProductName import ProductName
from WindowAutomator import WindowAutomator,Controller


class JDScraper:
    """
    检查京东到货信息
    """
    #存入的cookies信息
    COOKIE_FILE = "jd_cookies.json"

    def __init__(self, controller = None , url = None ,user_agent=None, viewport=None, headless=False ,idDelectStart=None , custom_db_config = None ):
        self.controller = controller or Controller()
        self.url = url or "https://mall.jd.com/view_search-1601455-13791745-99-1-24-1.html"
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"
        self.viewport = viewport or {"width": 1920, "height": 1080}
        self.headless = headless
        self.idDelectStart = idDelectStart or "J_"
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.api_responses = []
        self.api_data = []  # 存储所有API调用记录的列表 id_list = [item["parsed_data"]["id"] for item in api_data if item["parsed_data"]]
        self.id_list = [] # 处理获取到的数据，转化为可以用数据库读取的数据。
        self.qianLogin = False #用来记录再次之前是否进入过登录页面。主要用于避免api获取时，重复调用比较函数def check_response_login()
        self.mySQL = ProductName(custom_db_config or {
                'password': '8878338han',
                'database': 'printingpaper',#测试数据表:test,实际数据表:printingpaper
            })

    def __enter__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            channel="msedge",
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        self.context = self.browser.new_context(
            user_agent=self.user_agent,
            viewport=self.viewport
        )
        self.page = self.context.new_page()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def _save_cookies(self):
        cookies = self.context.cookies()
        with open(self.COOKIE_FILE, "w") as f:
            json.dump(cookies, f)
        print("Cookies已保存！")

    def _load_cookies(self):
        with open(self.COOKIE_FILE, "r") as f:
            cookies = json.load(f)
        self.context.add_cookies(cookies)
        print("Cookies已加载！")

    def _handle_captcha(self,yanZhengURL):
        print("尝试自动完成滑块验证...")
        #执行JDSliderVerifier.class
        v = JDSliderVerifier(yanZhengUrl=yanZhengURL, page=self.page)
        v.run()
        self.page.wait_for_selector("#captcha-container", state="hidden", timeout=120000)
        print("验证码处理完成！")
        self._save_cookies()

    def _login(self):
        print("请手动完成登录...时间30秒")
        with self.page.expect_response(
                lambda r: r.url == "https://api.m.jd.com/api",
                timeout=30000
        ) as response_info:
            pass
        response = response_info.value
        result = response.json()
        if result.get("code") == 0 and result.get("message") == "Success":
            print("✅ 登录成功")
            self._save_cookies()
            return True
        else:
            print("❌ 登录失败")
            #raise Exception(f"验证失败: {result.get('msg', '未知错误')}")
            return False

        # time.sleep(30)
        # if "https://passport.jd.com/new/login.aspx?" in self.page.url:
        #     print(f"登录处理失败，重新尝试登录{self.page.url,response.url}")
        #     self._login(response)
        # else:

    #落后方法，弃用
    def _monitor_api(self):
        def check_response(response):
            if response.url.startswith("https://api.m.jd.com/"):
                self.api_responses.append(response)
                if response.url.startswith("https://api.m.jd.com/?functionId=mGetsByColor&"):
                    print("--------------------------最原始的到货数据--------------------------------------")
                    print("URL:", response.url)
                    print("Status:", response.status)
                    print("Body:", response.json())
                    print(self.api_json_functionId(response))
                    print("-----------------------------------------------------------------------------")
            if "https://cfe.m.jd.com/privatedomain/risk_handler/03101900/?returnurl=https" in response.url:
                print("检测到验证码页面，开始处理...")
                self._handle_captcha()

        self.page.on("response", check_response)
        self.page.goto(self.url)
        self.page.wait_for_timeout(10000)

    def _monitor_api_main(self,FunctionName):
        self.page.on("response", FunctionName)
        self.page.goto(self.url,timeout=10000)
        self.page.wait_for_timeout(3000)

    def check_response(self,response):
        '''在成功加载进入登录页面后，也会随时获取api这是def _monitor_api_main(self,FunctionName):方法决定的。
        这时就会出现每获取一个api都要执行下面这个方法，因为处于登录页面，就会一直重复执行该方法。
        解决问题：一但进入登录页面后，就不在执行以下方法。
        需要一个参数，用来记录之前是否属于登录界面即可。'''
        if not self.qianLogin :
            self.check_response_login(response)
        self.check_response_验证(response)
        if response.url.startswith("https://api.m.jd.com/"):
            self.api_responses.append(response)
            if response.url.startswith("https://api.m.jd.com/?functionId=mGetsByColor&"):
                # 创建数据记录字典
                record = {
                    "url": response.url,
                    "status": response.status,
                    "timestamp": time.time(),  # 记录时间戳
                    #"parameters": self._parse_url_params(response.url),  # 解析URL参数
                    "body": None,
                    "parsed_data": None   # 记录当前url所传入的数据。
                }
                try:
                    # 尝试获取JSON数据
                    record["parsed_data"] = self.api_json_functionId(response,self.idDelectStart)
                except Exception as e:
                    record["error"] = str(e)
                self.api_data.append(record)
                print(f"捕获到第 {len(self.api_data)} 次API调用：时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record['timestamp']))}")
                # print(f"时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record['timestamp']))}")
                print(f"参数：{record['parsed_data']}")

    def check_response_login(self,response):
        if "https://passport.jd.com/new/login.aspx?" in self.page.url:
            print(f"检测到登录页面，开始处理...{self.page.url,response.url}")
            self.qianLogin = True
            if not self._login():
                print("❌登录失败，再次登录")

    def check_response_验证(self, response):
        if "https://cfe.m.jd.com/privatedomain/risk_handler/03101900/?returnurl=https" in response.url:
            print(f"检测到验证码页面，开始处理...{self.page.url,response.url}")
            self._handle_captcha(response.url)

    @staticmethod
    def api_json_stocks(response):
        try:
            stocks = response.json()
            return ["1" if sanCengData.get("StockStateName") == "现货" else "0"
                    for sanCengData in stocks.values()]
        except Exception as e:
            print(f"解析json失败:{e}")
            return []

    def _extract_valid_ids(self) -> List[str]:
        """安全提取有效商品ID"""
        valid_ids = []
        for item in self.api_data:
            try:
                parsed_data = item.get('parsed_data')
                #print(f"11111{parsed_data}")
                # 直接获取id字段
                for item in parsed_data:
                    product_id = item.get('id')
                # 验证有效性
                    if product_id and isinstance(product_id, (str, int)):
                        valid_ids.append(str(product_id))
            except (KeyError, TypeError) as e:
                # 日志输出 logger.warning(f"无效数据格式，跳过条目: {e}")
                continue
        print(f"获取到的数据id{valid_ids}")
        return valid_ids
    @staticmethod
    def api_json_functionId(response, idDelectStart=None):
        try:
            stocks = response.json()
            result = []
            for item in stocks:
                # 提取原始 p 和 id
                p = item["p"]
                original_id = item["id"]

                # 处理 id 截断逻辑
                processed_id = original_id
                if idDelectStart:  # 仅当参数存在且非空时处理
                    if original_id.startswith(idDelectStart):
                        processed_id = original_id[len(idDelectStart):]

                # 构建结果字典
                result.append({"p": p, "id": processed_id})
            return result
        except Exception as e:
            print(f"参数解析失败：{e}")
            return []  # 返回空列表保持类型一致

    def page_refresh(self):
        """
        目前为测试方法
        用于控制定时刷新页面，获取新数据
        :return:
        """
        #   等待时间
        random_number = random.randint(1000, 4000)
        print(f"------------------等待{random_number/1000}秒后刷新--------------------------")
        self.page.wait_for_timeout(random_number)
        # 刷新数据
        # self.refresh_self()
        #   刷新页面
        self.page.reload()


    def refresh_self(self):
        """刷新self中需要重置的数据的数据"""
        # 刷新id_list数据
        # print("------------------刷新前的id数据-------------------")
        # print(self.id_list)
        self.api_responses = []
        self.api_data = []
        self.id_list = []


    #获取商品在数据库中的名称,落后，已被def get_product_names()方法取代
    def get_apiData_mysqlName(self,custom_db_config):
        """
        获取apidata数据在数据库中对应的名称
        :param custom_db_config: 数据库的用户名密码
        :return:
        """
        try:
            # 使用上下文管理器自动处理连接
            with ProductName(self.api_data, db_config=custom_db_config) as product_query:
                names = product_query.get_product_names1()
                #print(f"查询结果: {names}")
                # 扩展使用示例
                for product_id, name in names.items():
                    print(f"ID: {product_id} => 名称: {name}")

        except Exception as e:
            pass
            #logger.error(f"处理过程中发生错误: {e}")

    def get_product_names(self) -> Dict[str, str]:
        """主流程方法：获取商品名称"""
        self.id_list = self._extract_valid_ids()
        # 如果id为空，直接跳过查询流程
        if not self.id_list:
            return  None
        return self.mySQL.get_product_names1(self.id_list)

    def _print_window(self,data):
        """主流程方法：发送信息给第一消息人"""
        weiXing = WindowAutomator("微信")
        if weiXing.send_message(message=data):
            self.controller.stop_requested.set()
    def _montageString(self,idAndName):
        """
            拼接京东商品链接及对应名称的字符串

            处理逻辑：
            1. 根据模板生成基础URL
            2. 添加空格作为分隔符
            3. 添加商品名称（从字典中查找）

            返回格式示例：
            https://item.jd.com/100020829196.html 未查询到
            """
        # 初始化结果列表
        result_lines = []

        # 遍历所有商品ID
        for product_id in self.id_list:
            # 1. 生成基础URL (使用字符串格式化的f-string语法)
            base_url = f"https://item.jd.com/{product_id}.html"

            # 2. 从字典中获取商品名称，使用get()方法避免KeyError
            #    如果找不到对应ID，使用默认值"未知商品"
            product_name = idAndName.get(product_id, " ")

            # 3. 拼接完整字符串: URL + 空格 + 商品名称
            full_string = f"{base_url} {product_name}"

            # 添加到结果列表
            result_lines.append(full_string)

        # 使用换行符连接所有结果
        return "\n".join(result_lines)


    def execute(self):
        """
        该流程执行获取并优化self.id_list中的数据
        数据库查询self.id_list所对应的名称，
        以及将查询到的self.id_list及对应数据发送给第一消息人。
        当所有流程执行完成后，清理本次流程获取到的数据，为下一次循环时的数据时效性做准备
        :return:
        """
        try:
            idAndName = self.get_product_names()
            if idAndName is None:
                return
            self._print_window(data=self._montageString(idAndName))

        except Exception as e:
            print("发生错误:", e)
        finally:# 必须执行数据清除
            self.refresh_self()

    def run(self):
        try:
            if os.path.exists(self.COOKIE_FILE) and os.path.getsize(self.COOKIE_FILE) > 0:
                self._load_cookies()
            self.page.wait_for_load_state("networkidle")
            self._monitor_api_main(self.check_response)
            max_executions = 200  # 最大执行次数
            timeout = 60*30  # 秒*分钟
            start_time = time.time()
            for i in range(max_executions):
                # 1. 检查停止信号（紧急停止）
                if self.controller.stop_requested.is_set():
                    print("! 收到停止指令，终止执行")
                    return

                # 检查超时
                if time.time() - start_time > timeout:
                    print("执行超时，自动终止")
                    return

                # 执行核心任务
                self.execute()
                self.page_refresh()

                # # 处理队列中的新指令 (非阻塞检查)
                self.process_pending_commands()

        except Exception as e:
            print("发生错误:", e)
            print(traceback.format_exc())
        finally:
            pass


    def process_pending_commands(self):
        """处理等待中的指令"""
        # 获取队列中的所有指令（非阻塞）
        while not self.controller.command_queue.empty():
            command = self.controller.command_queue.get()
            print(f"处理指令: {command}")

            if command == "STOP":
                self.controller.stop_requested.set()
            elif command == "PAUSE":
                self.controller.pause_requested.set()
            elif command == "RESUME":
                self.controller.pause_requested.clear()




if __name__ == "__main__":
    拍立得相纸地址 = "https://mall.jd.com/view_search-1601455-13791745-99-1-24-1.html"
    TARGET_URL = "https://mg-pen.jd.com/view_search-395842-20898628-5-1-24-1.html"
    jzt = "https://jzt-admin.qimingdaren.com/"

    with JDScraper(
            url=拍立得相纸地址,
            headless=False  # 调试时可设置为False显示浏览器
    ) as scraper:
        scraper.run()