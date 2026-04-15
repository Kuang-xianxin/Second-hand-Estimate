"""
OpenCLI 适配层
将 OpenCLI 的浏览器自动化能力集成到后端服务

支持:
- 闲鱼商品搜索 (使用后端 xianyu.py，不走 OpenCLI)
- Bilibili 热门榜单
- GitHub Trending
- 浏览器截图
- 其他 OpenCLI 支持的网站

注意: 闲鱼爬虫保留后端原生实现 (backend/app/crawler/xianyu.py)，
因为闲鱼数据是核心业务，需要精细化处理。
"""
import asyncio
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class OpenCLIAdapter:
    """
    OpenCLI 统一适配器
    通过 subprocess 调用 opencli 命令
    """

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self._check_installed()

    def _check_installed(self) -> bool:
        """检查 OpenCLI 是否已安装"""
        try:
            result = subprocess.run(
                ["opencli", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(f"OpenCLI 已安装: {result.stdout.strip()}")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        logger.warning("OpenCLI 未安装，跳过初始化")
        return False

    def _run_command(self, args: List[str], timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        执行 opencli 命令

        Args:
            args: 命令参数列表，如 ["xianyu", "search", "iPhone"]
            timeout: 超时秒数

        Returns:
            包含 returncode, stdout, stderr 的字典
        """
        if timeout is None:
            timeout = self.timeout

        try:
            result = subprocess.run(
                ["opencli"] + args,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            logger.error(f"OpenCLI 命令超时: {' '.join(args)}")
            return {"returncode": -1, "stdout": "", "stderr": "Timeout", "success": False}
        except FileNotFoundError:
            logger.error("OpenCLI 未安装，请运行: npm install -g @jackwener/opencli")
            return {"returncode": -1, "stdout": "", "stderr": "OpenCLI not found", "success": False}

    # ─────────────────────────────────────────────────────────────
    # 闲鱼相关 (转发到后端 xianyu.py，这里仅作标记)
    # ─────────────────────────────────────────────────────────────

    async def search_xianyu(self, keyword: str, limit: int = 20) -> Dict[str, Any]:
        """
        闲鱼搜索 - 注意: 此方法仅作文档说明
        实际闲鱼爬虫使用 backend/app/crawler/xianyu.py

        返回示例:
        {
            "source": "xianyu_crawler",
            "message": "使用后端原生爬虫，详见 xianyu.py"
        }
        """
        return {
            "source": "xianyu_crawler",
            "message": "闲鱼搜索使用后端原生爬虫 backend/app/crawler/xianyu.py",
            "recommendation": "请直接使用 XianyuCrawler 类"
        }

    # ─────────────────────────────────────────────────────────────
    # Bilibili 相关
    # ─────────────────────────────────────────────────────────────

    async def get_bilibili_hot(self, limit: int = 10, category: str = "all") -> Dict[str, Any]:
        """
        获取 Bilibili 热门视频

        Args:
            limit: 返回数量
            category: 分类 (all/pgc/ranking)

        Returns:
            热门视频列表
        """
        args = ["bilibili", "hot", "--limit", str(limit)]
        if category != "all":
            args.extend(["--category", category])

        result = self._run_command(args + ["-f", "json"])
        if not result["success"]:
            return {"error": result["stderr"], "items": []}

        try:
            data = json.loads(result["stdout"])
            return {"items": data if isinstance(data, list) else [data]}
        except json.JSONDecodeError:
            return {"raw": result["stdout"], "items": []}

    async def search_bilibili(self, keyword: str, limit: int = 10) -> Dict[str, Any]:
        """搜索 Bilibili 视频"""
        result = self._run_command([
            "bilibili", "search", keyword,
            "--limit", str(limit),
            "-f", "json"
        ])

        if not result["success"]:
            return {"error": result["stderr"], "items": []}

        try:
            data = json.loads(result["stdout"])
            return {"items": data if isinstance(data, list) else [data]}
        except json.JSONDecodeError:
            return {"raw": result["stdout"], "items": []}

    # ─────────────────────────────────────────────────────────────
    # GitHub 相关
    # ─────────────────────────────────────────────────────────────

    async def github_trending(self, language: str = "", since: str = "daily") -> Dict[str, Any]:
        """
        获取 GitHub Trending

        Args:
            language: 编程语言筛选 (python/go/js/...)
            since: 时间范围 (daily/weekly/monthly)
        """
        args = ["github", "trending"]
        if language:
            args.extend(["--language", language])
        args.extend(["--since", since, "-f", "json"])

        result = self._run_command(args)
        if not result["success"]:
            return {"error": result["stderr"], "items": []}

        try:
            data = json.loads(result["stdout"])
            return {"items": data if isinstance(data, list) else [data]}
        except json.JSONDecodeError:
            return {"raw": result["stdout"], "items": []}

    # ─────────────────────────────────────────────────────────────
    # 浏览器控制 (需要 Chrome 扩展)
    # ─────────────────────────────────────────────────────────────

    async def browser_open(self, url: str) -> Dict[str, Any]:
        """打开浏览器并访问 URL"""
        result = self._run_command(["browser", "open", url], timeout=30)
        return {
            "success": result["success"],
            "message": "浏览器已打开" if result["success"] else result["stderr"]
        }

    async def browser_screenshot(self, url: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        截取网页截图

        Args:
            url: 目标 URL
            output_path: 保存路径，默认 temp 文件

        Returns:
            截图文件路径
        """
        if not output_path:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                output_path = f.name

        result = self._run_command([
            "browser", "open", url,
            "--screenshot", output_path
        ], timeout=60)

        return {
            "success": result["success"],
            "path": output_path if result["success"] else None,
            "error": result["stderr"] if not result["success"] else None
        }

    async def browser_extract(self, url: str, selector: str) -> Dict[str, Any]:
        """
        从页面提取内容

        Args:
            url: 目标 URL
            selector: CSS 选择器
        """
        result = self._run_command([
            "browser", "open", url,
            "--extract", selector
        ], timeout=60)

        if not result["success"]:
            return {"error": result["stderr"], "content": ""}

        return {"content": result["stdout"].strip()}

    # ─────────────────────────────────────────────────────────────
    # 其他网站适配器
    # ─────────────────────────────────────────────────────────────

    async def reddit_hot(self, subreddit: str = "", limit: int = 10) -> Dict[str, Any]:
        """Reddit 热门帖子"""
        args = ["reddit", "hot"]
        if subreddit:
            args.extend(["--subreddit", subreddit])
        args.extend(["--limit", str(limit), "-f", "json"])

        result = self._run_command(args)
        if not result["success"]:
            return {"error": result["stderr"], "items": []}

        try:
            return {"items": json.loads(result["stdout"])}
        except json.JSONDecodeError:
            return {"raw": result["stdout"], "items": []}

    async def twitter_search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Twitter/X 搜索"""
        result = self._run_command([
            "twitter", "search", query,
            "--limit", str(limit),
            "-f", "json"
        ])

        if not result["success"]:
            return {"error": result["stderr"], "items": []}

        try:
            return {"items": json.loads(result["stdout"])}
        except json.JSONDecodeError:
            return {"raw": result["stdout"], "items": []}

    async def zhihu_hot(self, limit: int = 10) -> Dict[str, Any]:
        """知乎热榜"""
        result = self._run_command([
            "zhihu", "hot",
            "--limit", str(limit),
            "-f", "json"
        ])

        if not result["success"]:
            return {"error": result["stderr"], "items": []}

        try:
            return {"items": json.loads(result["stdout"])}
        except json.JSONDecodeError:
            return {"raw": result["stdout"], "items": []}

    # ─────────────────────────────────────────────────────────────
    # 工具方法
    # ─────────────────────────────────────────────────────────────

    async def list_commands(self) -> List[str]:
        """列出所有可用的 OpenCLI 命令"""
        result = self._run_command(["list"])
        if result["success"]:
            # 解析命令列表
            lines = result["stdout"].strip().split("\n")
            return [line.strip() for line in lines if line.strip() and not line.startswith("#")]
        return []

    async def check_health(self) -> Dict[str, Any]:
        """检查 OpenCLI 运行状态"""
        doctor_result = self._run_command(["doctor"], timeout=30)

        # 也检查浏览器连接
        browser_check = self._run_command(["browser", "state"], timeout=10)

        return {
            "opencli_installed": result.returncode == 0 if (result := self._run_command(["--version"], 5)) else False,
            "doctor_passed": doctor_result["success"],
            "browser_connected": browser_check["success"],
            "doctor_output": doctor_result.get("stdout", ""),
            "browser_state": browser_check.get("stdout", "").strip()
        }


# 全局单例
_opencli_adapter: Optional[OpenCLIAdapter] = None


def get_opencli_adapter() -> OpenCLIAdapter:
    """获取 OpenCLI 适配器单例"""
    global _opencli_adapter
    if _opencli_adapter is None:
        _opencli_adapter = OpenCLIAdapter()
    return _opencli_adapter
