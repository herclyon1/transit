#!/bin/sh
# 共享资源锁（模拟器 / Maps 窗口）。锁文件在仓库外 ~/Money/.locks/<资源>，内容 = 谁 + 何时。
# 用法：pipeline/lock.sh take simulator ui    占用（已被别人占用则失败并打印占用者）
#       pipeline/lock.sh free simulator ui    释放（只能释放自己的）
#       pipeline/lock.sh show                 看全部锁
D=$HOME/Money/.locks; mkdir -p "$D"
case "$1" in
  take) f="$D/$2"; if [ -f "$f" ] && ! grep -q "^$3 " "$f"; then echo "被占用：$(cat "$f")"; exit 1; fi
        echo "$3 $(date '+%F %H:%M')" > "$f"; echo "已占用 $2：$(cat "$f")";;
  free) f="$D/$2"; if [ -f "$f" ] && ! grep -q "^$3 " "$f"; then echo "不是你的锁：$(cat "$f")"; exit 1; fi
        rm -f "$f"; echo "已释放 $2";;
  show) for f in "$D"/*; do [ -f "$f" ] && echo "$(basename "$f")：$(cat "$f")"; done; [ -n "$(ls "$D")" ] || echo "无锁";;
  *) sed -n 2,5p "$0";;
esac
