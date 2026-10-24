#!/usr/bin/env bash
# Arranca el vigía en segundo plano (sesión tmux, por defecto "vigia") con log en la carpeta de casos.
# Para vigilar otra impresora a la vez: otra copia del proyecto con su .env y VIGIA_SESION distinto.
cd "$(dirname "$0")"
valor() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2-; }
D=$(valor DIR_CASOS); D=${D:-casos}
S=$(valor VIGIA_SESION); S=${S:-vigia}
mkdir -p "$D"
tmux kill-session -t "$S" 2>/dev/null
[ "$S" = vigia ] && tmux kill-session -t monitor 2>/dev/null   # el monitor antiguo, si sigue vivo
tmux new -d -s "$S" "./venv/bin/python -m vigia 2>&1 | tee -a '$D/vigia.log'"
echo "✅ Vigía arrancado (sesión $S). Log: $D/vigia.log"
echo "   Verlo:  tmux attach -t $S    (salir sin pararlo: Ctrl+B y luego D)"
echo "   Pararlo: tmux kill-session -t $S"
