#!/bin/bash
# 电量安全阀：夜间任务每完成一个子任务后调用，判断是否需要紧急落盘收尾。
#
# 背景：2026-09-24 任务被 DarkWake 掐断导致产出全丢；拔电场景下更糟——
#       电量耗尽是直接关机，连 commit 的机会都没有。本脚本让任务在电量见底前
#       主动收尾，至少保住已完成的部分。
#
# 用法：
#   ./power_check.sh            # 默认阈值 25%
#   ./power_check.sh 40         # 自定义阈值 40%
#
# 退出码：
#   0  安全：AC 供电，或电量 ≥ 阈值（可继续跑）
#   2  危险：电池供电且电量 < 阈值（应立即 git commit + 写报告 + 优雅退出）
#   3  无法读取电量（视为安全，不阻断任务，但报告里记录异常）
#
# 输出（便于抄进夜间报告）：
#   POWER source=AC percent=-- safe=1 threshold=25 reason=ac_power
#   POWER source=BATTERY percent=18 safe=0 threshold=25 reason=low_battery

THRESHOLD="${1:-${NIGHT_BATTERY_MIN:-25}}"

raw="$(pmset -g batt 2>/dev/null)"
if [ -z "$raw" ]; then
  echo "POWER source=UNKNOWN percent=-- safe=1 threshold=$THRESHOLD reason=read_failed"
  exit 3
fi

if echo "$raw" | grep -q "AC Power"; then
  src="AC"
else
  src="BATTERY"
fi

pct="$(echo "$raw" | grep -oE '[0-9]+%' | head -1 | tr -d '%')"
if [ -z "$pct" ]; then
  pct="--"
fi

if [ "$src" = "AC" ]; then
  echo "POWER source=AC percent=${pct} safe=1 threshold=${THRESHOLD} reason=ac_power"
  exit 0
fi

if [ "$pct" = "--" ]; then
  echo "POWER source=BATTERY percent=-- safe=1 threshold=${THRESHOLD} reason=percent_unknown"
  exit 3
fi

if [ "$pct" -lt "$THRESHOLD" ]; then
  echo "POWER source=BATTERY percent=${pct} safe=0 threshold=${THRESHOLD} reason=low_battery"
  exit 2
fi

echo "POWER source=BATTERY percent=${pct} safe=1 threshold=${THRESHOLD} reason=above_threshold"
exit 0
