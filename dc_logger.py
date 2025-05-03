# dc_logger.py
import sys
import traceback
import datetime
import os

LOG_VERSION = "v1.2.0"
# 항상 이 파일이 있는 디렉토리에 로그 파일 생성
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(PROJECT_ROOT, f"error_log_{LOG_VERSION}.txt")

LOG_LEVELS = {"DEBUG":0, "INFO":1, "WARN":2, "ERROR":3}
CURRENT_LEVEL = LOG_LEVELS["DEBUG"]  # 최소 출력 레벨


def _log(msg, level="INFO", module=None, exc_info=None):
    if LOG_LEVELS[level] < CURRENT_LEVEL:
        return
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mod = f"[{module}]" if module else ""
    line = f"[{LOG_VERSION}] [{ts}] [{level}]{mod} {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            if exc_info:
                tb = ''.join(traceback.format_exception(*exc_info))
                f.write(tb + "\n")
                print(tb, file=sys.stderr)
    except Exception as e:
        print(f"[LOGGER ERROR] 로그 파일 생성/쓰기 실패: {e}", file=sys.stderr)
        print(f"[LOGGER ERROR] 경로: {LOG_FILE}", file=sys.stderr)

def log_debug(msg, module=None):
    _log(msg, level="DEBUG", module=module)

def log_info(msg, module=None):
    _log(msg, level="INFO", module=module)

def log_warn(msg, module=None):
    _log(msg, level="WARN", module=module)

def log_error(msg, module=None, exc_info=None):
    _log(msg, level="ERROR", module=module, exc_info=exc_info)

# 기존 log 함수와 호환
log = log_info

def log_task_start(task_name, module=None):
    _log(f"[TASK START] {task_name}", level="INFO", module=module)

def log_task_end(task_name, module=None):
    _log(f"[TASK END] {task_name}", level="INFO", module=module)
