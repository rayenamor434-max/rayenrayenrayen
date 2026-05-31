"""
JARVIS OMEGA — System Monitor Agent
CPU, RAM, disk, battery, processes — optimized for low-end PCs.
"""
import os
import platform
from typing import Dict, List
from datetime import datetime


class SystemMonitor:
    def __init__(self):
        self._psutil_ok = self._check_psutil()

    @staticmethod
    def _check_psutil() -> bool:
        try:
            import psutil
            return True
        except ImportError:
            return False

    def get_full_report(self) -> Dict:
        if not self._psutil_ok:
            return self._basic_report()
        
        import psutil
        
        cpu_pct = psutil.cpu_percent(interval=0.5)
        cpu_freq = psutil.cpu_freq()
        
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        disk = psutil.disk_usage('/')
        
        battery = None
        try:
            bat = psutil.sensors_battery()
            if bat:
                battery = {
                    "percent": round(bat.percent, 1),
                    "plugged": bat.power_plugged,
                    "time_left": str(bat.secsleft // 60) + "min" if bat.secsleft > 0 else "N/A"
                }
        except Exception:
            pass
        
        net = {}
        try:
            net_io = psutil.net_io_counters()
            net = {
                "bytes_sent_mb": round(net_io.bytes_sent / 1024 / 1024, 1),
                "bytes_recv_mb": round(net_io.bytes_recv / 1024 / 1024, 1),
            }
        except Exception:
            pass
        
        return {
            "cpu": {
                "percent": cpu_pct,
                "cores_logical": psutil.cpu_count(logical=True),
                "cores_physical": psutil.cpu_count(logical=False),
                "freq_mhz": round(cpu_freq.current, 0) if cpu_freq else None,
            },
            "ram": {
                "total_gb": round(mem.total / 1e9, 1),
                "used_gb": round(mem.used / 1e9, 1),
                "available_gb": round(mem.available / 1e9, 1),
                "percent": mem.percent,
            },
            "swap": {
                "total_gb": round(swap.total / 1e9, 1),
                "used_gb": round(swap.used / 1e9, 1),
                "percent": swap.percent,
            },
            "disk": {
                "total_gb": round(disk.total / 1e9, 1),
                "used_gb": round(disk.used / 1e9, 1),
                "free_gb": round(disk.free / 1e9, 1),
                "percent": disk.percent,
            },
            "battery": battery,
            "network": net,
            "platform": platform.system(),
            "hostname": platform.node(),
            "python": platform.python_version(),
            "timestamp": datetime.now().isoformat(),
        }

    def get_top_processes(self, limit: int = 8) -> List[Dict]:
        if not self._psutil_ok:
            return []
        import psutil
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = p.info
                procs.append({
                    "pid": info['pid'],
                    "name": info['name'][:30],
                    "cpu": round(info['cpu_percent'] or 0, 1),
                    "mem": round(info['memory_percent'] or 0, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(key=lambda x: x['cpu'], reverse=True)
        return procs[:limit]

    def format_report(self, report: Dict) -> str:
        if "error" in report:
            return report["error"]
        
        lines = []
        cpu = report.get("cpu", {})
        ram = report.get("ram", {})
        disk = report.get("disk", {})
        bat = report.get("battery")
        
        lines.append(f"CPU: {cpu.get('percent', '?')}% | {cpu.get('cores_logical', '?')} cores"
                     + (f" @ {cpu.get('freq_mhz', '?')}MHz" if cpu.get('freq_mhz') else ""))
        lines.append(f"RAM: {ram.get('used_gb', '?')}/{ram.get('total_gb', '?')}GB "
                     f"({ram.get('percent', '?')}% used)")
        lines.append(f"Disk: {disk.get('used_gb', '?')}/{disk.get('total_gb', '?')}GB "
                     f"({disk.get('percent', '?')}% used)")
        if bat:
            status = "🔌" if bat['plugged'] else "🔋"
            lines.append(f"Battery: {status} {bat['percent']}%")
        
        return " | ".join(lines)

    def _basic_report(self) -> Dict:
        return {
            "error": "psutil not installed. Run: pip install psutil",
            "platform": platform.system(),
            "timestamp": datetime.now().isoformat(),
        }

    def get_performance_advice(self) -> str:
        """Returns advice if system is under stress."""
        if not self._psutil_ok:
            return ""
        import psutil
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory().percent
        
        warnings = []
        if cpu > 80:
            warnings.append(f"CPU at {cpu}% — consider closing heavy apps")
        if mem > 85:
            warnings.append(f"RAM at {mem}% — memory pressure detected")
        
        return "; ".join(warnings) if warnings else ""
