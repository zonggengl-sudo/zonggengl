#!/bin/bash
# 夜间防睡眠守护（配合每晚 23:00 的 HY4 批处理任务）
#
# 背景：2026-09-24 任务跑 33 分钟后被掐断，根因是 Mac 用电池进 Deep Idle，
#       只在 DarkWake 暗唤醒窗口里启动，系统退回睡眠时连接被杀。
# 本脚本在夜间窗口拉起 caffeinate 持有系统级防睡断言，作为 pmset 之外的第二道保险。
#
# 用法：
#   ./night_guard.sh start    # 拉起防睡（AC 供电时最有效）
#   ./night_guard.sh stop     # 释放防睡，恢复正常睡眠
#   ./night_guard.sh status   # 查看当前供电、防睡断言、caffeinate 状态
#
# 建议定时（已写入 crontab）：
#   55 22 * * *  .../night_guard.sh start
#   05 08 * * *  .../night_guard.sh stop

PIDFILE="/tmp/night_caffeinate.pid"
LOG="/tmp/night_guard.log"

ts() { date '+%F %T'; }
log() { echo "$(ts) $*" >> "$LOG"; }

is_ac() { pmset -g ps | grep -q "AC Power" && return 0 || return 1; }
# 汇总行的 PreventSystemSleep 在电池档会显示 0（`-s` 仅在 AC 生效），
# 但 caffeinate 明细里实际持有该断言（asserting forever）。只看汇总会误判，
# 所以以"caffeinate 进程是否活着"为准，并附上汇总值备查。
assertion() {
  if pgrep -x caffeinate >/dev/null 2>&1; then
    echo "1(caffeinate持有)"
  else
    echo "0(无防睡进程)"
  fi
}
assertion_raw() { pmset -g assertions 2>/dev/null | awk '/^   PreventSystemSleep/{print $2; exit}'; }
running_pid() {
  [ -f "$PIDFILE" ] || return 1
  local p; p=$(cat "$PIDFILE" 2>/dev/null)
  [ -n "$p" ] && kill -0 "$p" 2>/dev/null && echo "$p" && return 0
  return 1
}

start() {
  if running_pid >/dev/null; then
    log "already running pid=$(running_pid)"
  else
    # 必须脱离当前进程组：直接 `nohup ... &` 启动的 caffeinate 会随调用方
    # shell 退出而被回收（2026-09-30 实测：下一个调用里进程已死，防睡形同虚设）。
    # 用 Python 的 start_new_session=True（底层 setsid）真正脱离会话。
    python3 -c 'import subprocess,sys; subprocess.Popen(["caffeinate","-siu"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)' 2>/dev/null
    sleep 1
    echo "$(pgrep -x caffeinate | tail -1)" > "$PIDFILE"
  fi
  sleep 2
  if is_ac; then
    log "started pid=$(running_pid) AC=1 PreventSystemSleep=$(assertion)"
  else
    log "started pid=$(running_pid) AC=0 ⚠️ 电池供电，DarkWake 风险仍在，请接电源"
  fi
  status
}

stop() {
  local p; p=$(running_pid)
  if [ -n "$p" ]; then
    kill "$p" 2>/dev/null && log "stopped pid=$p"
    rm -f "$PIDFILE"
  else
    log "not running"
  fi
  status
}

status() {
  if is_ac; then pw="AC Power ✅"; else pw="Battery ⚠️"; fi
  if [ -n "$(running_pid)" ]; then cf="运行中 pid=$(running_pid)"; else cf="未运行"; fi
  echo "供电        : $pw"
  echo "电量        : $(pmset -g batt 2>/dev/null | grep -oE '[0-9]+%' | head -1 || echo 未知)$( [ "$pw" = "Battery ⚠️" ] && echo "   ⚠️ 低于 25% 时 power_check.sh 会要求紧急收尾" )"
  echo "caffeinate  : $cf"
  echo "防睡断言    : $(assertion)  （pmset 汇总值=$(assertion_raw)；电池档下汇总值恒为 0 属正常，以 caffeinate 进程为准）"
  echo "睡眠定时器  : $(pmset -g | awk '/^ sleep/{print $2}')  (0=不会自动睡)"
  echo "standby     : $(pmset -g | awk '/^ standby/{print $2}')"
  echo "powernap    : $(pmset -g | awk '/^ powernap/{print $2}')"
}

case "$1" in
  start)   start ;;
  stop)    stop ;;
  status)  status ;;
  *)       echo "用法: $0 {start|stop|status}" ; exit 1 ;;
esac
