import pymysql
from typing import List, Dict, Optional
import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProductName:
    """京东商品名称查询器"""

    def __init__(self, api_data: List[dict] = None , db_config: Optional[dict] = None):
        """
        初始化商品名称查询器

        :param api_data: 原始API数据（包含商品ID）
        :param db_config: 可选的数据库配置字典，格式示例：
            {
                'host': 'localhost',
                'port': 3306,
                'user': 'root',
                'password': 'your_password',
                'database': 'your_db',
                'charset': 'utf8mb4'
            }
        """
        self.api_data = api_data
        #self.id_list = self._extract_valid_ids()
        self.conn = None
        self.cursor = None
        self.db_config = self._get_db_config(db_config)
        #self._connect_db()
        self._connect()

    def _set_api_data(self,api_data):
        self.api_data = api_data

    def _connect(self):
        """建立数据库连接"""
        try:
            self.conn = pymysql.connect(**self.db_config)
            logger.info("数据库连接成功")
        except pymysql.Error as e:
            logger.error(f"数据库连接失败: {e}")
            raise RuntimeError("数据库连接失败") from e

    def _ensure_connection(self):
        """确保连接有效"""
        try:
            self.conn.ping(reconnect=True)
        except Exception:
            self._connect()

    def _extract_valid_ids(self) -> List[str]:
        """安全提取有效商品ID"""
        valid_ids = []
        for item in self.api_data:
            try:
                parsed_data = item.get('parsed_data')

                # 直接获取id字段
                for item in parsed_data:
                    product_id = item.get('id')
                # 验证有效性
                    if product_id and isinstance(product_id, (str, int)):
                        valid_ids.append(str(product_id))
            except (KeyError, TypeError) as e:
                logger.warning(f"无效数据格式，跳过条目: {e}")
                continue
        print(f"获取到的数据id{valid_ids}")
        return valid_ids

    def _get_db_config(self, custom_config: Optional[dict]) -> dict:
        """合并数据库配置"""
        default_config = {
            'host': 'localhost',
            'port': 3306,
            'user': 'root',
            'password': '8878338han',
            'database': 'polaroid',
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }
        return {**default_config, **(custom_config or {})}

    def _connect_db(self):
        """建立数据库连接"""
        try:
            self.conn = pymysql.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            logger.info("数据库连接成功")
        except pymysql.Error as e:
            logger.error(f"数据库连接失败: {e}")
            raise RuntimeError("数据库连接失败") from e

    def get_product_names(self) -> Dict[str, str]:
        """
        批量获取商品名称

        :return: 格式 {商品ID: 商品名称}
        """
        if not self.id_list:
            logger.warning("没有有效的商品ID可供查询")
            return {}

        try:
            # 创建临时表实现批量查询
            with self.conn.cursor() as cursor:
                # 创建临时表
                cursor.execute("CREATE TEMPORARY TABLE temp_ids (id BIGINT(255) PRIMARY KEY)")

                # 批量插入ID
                batch_size = 1000
                for i in range(0, len(self.id_list), batch_size):
                    batch = [(id_,) for id_ in self.id_list[i:i + batch_size]]
                    cursor.executemany("INSERT IGNORE INTO temp_ids VALUES (%s)", batch)

                # 执行关联查询
                query = """
                    SELECT p.J_id, p.sname 
                    FROM test p
                    JOIN temp_ids t ON p.J_id = t.id
                """
                cursor.execute(query)
                results = cursor.fetchall()

            return {row['J_id']: row['sname'] for row in results} if results else {}

        except pymysql.Error as e:
            logger.error(f"数据库查询失败: {e}")
            self.conn.rollback()
            return {}
        finally:
            self.conn.commit()

    def get_product_names1(self, id_list: List[str]) -> Dict[str, str]:
        """
        批量获取商品名称，未找到的记录返回"未查询到"

        :return: 包含所有传入ID的字典 {商品ID: 商品名称或'未查询到'}
        """

        self._ensure_connection()

        if not id_list:
            logger.warning("没有有效的商品ID可供查询")
            return {}

        id_set = set(map(str, id_list))  # 统一ID格式并去重
        result = {id_: "未查询到" for id_ in id_set}  # 初始化默认值

        try:
            with self.conn.cursor() as cursor:
                # 创建支持重复的临时表
                cursor.execute("""
                    CREATE TEMPORARY TABLE temp_ids (
                        seq INT AUTO_INCREMENT PRIMARY KEY,
                        id VARCHAR(255) NOT NULL
                    ) 
                """)

                # 批量插入所有原始ID（包含重复）
                batch_size = 1000
                for i in range(0, len(id_list), batch_size):
                    batch = [(str(id_),) for id_ in id_list[i:i + batch_size]]
                    cursor.executemany("INSERT INTO temp_ids (id) VALUES (%s)", batch)

                # 执行关联查询
                query = """
                    SELECT t.id, COALESCE(p.sname, ' ') AS sname 
                    FROM temp_ids t
                    LEFT JOIN test p ON t.id = p.J_id
                    ORDER BY t.seq  -- 保持原始顺序
                """
                cursor.execute(query)


                # 更新查询结果
                for row in cursor.fetchall():
                    result[row['id']] = row['sname']
                #清理临时表
                cursor.execute("DROP TEMPORARY TABLE IF EXISTS temp_ids")
            return dict((k, result[str(k)]) for k in id_list)  # 保持原始输入格式

        except pymysql.Error as e:
            logger.error(f"数据库查询失败: {e}")
            return {id_: "未查询到" for id_ in id_list}
        finally:
            self.conn.commit()

    def close(self):
        """安全关闭数据库连接"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
                logger.info("数据库连接已关闭")
        except pymysql.Error as e:
            logger.error(f"关闭连接时出错: {e}")

    def __enter__(self):
        """支持上下文管理"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """自动关闭连接"""
        self.close()


# 使用示例
if __name__ == "__main__":
    # 模拟API数据
    mock_api_data = [{'p': '3.50', 'id': '100019518209'},
                     {'p': '7.90', 'id': '100088492570'},
                     {'p': '8.90', 'id': '100038797220'},
                     {'p': '15.90', 'id': '100027345571'},
                     {'p': '32.90', 'id': '100011159365'},
                     {'p': '21.90', 'id': '100085169747'},
                     {'p': '3.60', 'id': '100034410230'},
                     {'p': '2.90', 'id': '100019518231'},
                     {'p': '5.50', 'id': '100076891605'},
                     {'p': '12.80', 'id': '100149897498'}]
    mock_api_data1 = ({'url': 'https://api.m.jd.com/?functionId=mGetsByColor&appid=mall_jd_com&clientVersion=1.0.0&client=','status': 200, 'timestamp': 1746696116.5308757, 'body': None,
                       'parsed_data': [{'p': '9.90', 'id': '100020829196'}, {'p': '9.90', 'id': '100092080692'}, {'p': '4.59', 'id': '100019518217'}, {'p': '7.11', 'id': '100011159357'}, {'p': '7.16', 'id': '100078021391'}, {'p': '17.90', 'id': '100020829204'}, {'p': '14.90', 'id': '100020829206'}, {'p': '6.12', 'id': '100019518243'}, {'p': '7.20', 'id': '100061492486'}, {'p': '6.90', 'id': '100061492484'}]
                       },
                      {'url': 'https://api.m.jd.com/?functionId=mGetsByColor&appid=mall_jd_com&clientVersion=1.0.0&client=','status': 200, 'timestamp': 1746696116.536874, 'body': None,
                       'parsed_data': [{'p': '3.50', 'id': '100019518209'}, {'p': '9.00', 'id': '100088492570'}, {'p': '7.90', 'id': '100038797220'}, {'p': '4.05', 'id': '100132583249'}, {'p': '32.90', 'id': '100011159365'}, {'p': '21.90', 'id': '100085169747'}, {'p': '3.60', 'id': '100034410230'}, {'p': '2.90', 'id': '100019518231'}, {'p': '6.82', 'id': '100076891605'}, {'p': '12.80', 'id': '100149897498'}]
                       })

    # 使用自定义配置（可选）
    custom_db_config = {
        'password': '8878338han',
        'database': 'polaroid',
    }

    try:
        # 使用上下文管理器自动处理连接
        with ProductName(mock_api_data1, db_config=custom_db_config) as product_query:
            names = product_query.get_product_names1()
            print(f"查询结果: {names}")

            # 扩展使用示例
            for product_id, name in names.items():
                print(f"ID: {product_id} => 名称: {name}")

    except Exception as e:
        logger.error(f"处理过程中发生错误: {e}")