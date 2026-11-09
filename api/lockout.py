"""비밀번호 실패 잠금: (과제 id, IP)별 연속 5회 실패 시 15분. 프로세스 메모리 기반."""
import os
import threading
import time

from fastapi import Request

MAX_FAILURES = 5
LOCK_SECONDS = 900

# key -> [연속 실패 횟수, 잠금 해제 시각(monotonic, 0이면 잠금 아님)]
_state: dict[tuple[int, str], list[float]] = {}
_lock = threading.Lock()


def reset_lockout() -> None:
    """모든 카운터를 비운다(테스트용, HTTP로 노출하지 않음)."""
    with _lock:
        _state.clear()


def get_client_ip(request: Request) -> str:
    """기본은 소켓 peer 주소. TRUST_PROXY=1일 때만 X-Forwarded-For를 쓴다."""
    if os.environ.get("TRUST_PROXY") == "1":
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def locked_seconds(project_id: int, ip: str) -> int:
    """잠금 상태면 남은 초(1 이상), 아니면 0."""
    with _lock:
        entry = _state.get((project_id, ip))
        if not entry or entry[1] == 0:
            return 0
        remaining = entry[1] - time.monotonic()
        if remaining > 0:
            return max(1, int(remaining))
        del _state[(project_id, ip)]  # 잠금 만료
        return 0


def record_failure(project_id: int, ip: str) -> None:
    with _lock:
        entry = _state.setdefault((project_id, ip), [0, 0])
        entry[0] += 1
        if entry[0] >= MAX_FAILURES:
            entry[1] = time.monotonic() + LOCK_SECONDS


def record_success(project_id: int, ip: str) -> None:
    with _lock:
        _state.pop((project_id, ip), None)
