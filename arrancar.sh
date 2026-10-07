#!/usr/bin/env bash
# Arranca el vigía en segundo plano (sesión tmux "vigia") con log en la carpeta de casos.
cd "$(dirname "$0")"
D=$(grep -E '^DIR_CASOS=' .env 2>/dev/null | tail -1 | cut -d= -f2-)
D=${D:-casos}
mkdir -p "$D"
tmux kill-session -t vigia 2>/dev/null
tmux kill-session -t monitor 2>/dev/null   # el monitor antiguo, si sigue vivo
tmux new -d -s vigia "./venv/bin/python -m vigia 2>&1 | tee -a '$D/vigia.log'"
echo "✅ Vigía arrancado. Log: $D/vigia.log"
echo "   Verlo:  tmux attach -t vigia    (salir sin pararlo: Ctrl+B y luego D)"
echo "   Pararlo: tmux kill-session -t vigia"
