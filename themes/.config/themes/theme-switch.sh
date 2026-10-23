#!/bin/bash
# Catppuccin theme switcher.
#   theme-switch.sh <macchiato|mocha|frappe|latte>   apply a theme
#   theme-switch.sh pick                             rofi picker
#   theme-switch.sh restore                          re-render the saved theme (no reload)
#   theme-switch.sh cycle                            next theme in list
#
# Renders templates/* (placeholders like @@base@@) into each app's generated
# color file, then reloads whatever can be reloaded live.

set -uo pipefail

T="$HOME/.config/themes"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/theme"
mapfile -t THEMES < <(cd "$T/palettes" && ls *.pal | sed "s/\.pal$//")
mkdir -p "$STATE"

CMD="${1:-pick}"
CUR=$(cat "$STATE/current" 2>/dev/null || echo macchiato)

case "$CMD" in
    pick)
        # Row format: "<name> <color dots>" - name is always the first word.
        DOT=$(printf '\xe2\x97\x8f')
        rows=""
        for n in "${THEMES[@]}"; do
            sw=""
            for c in base lavender mauve blue green yellow peach red; do
                v=$(grep "^$c=" "$T/palettes/$n.pal" | cut -d= -f2)
                sw+="<span foreground='#$v'>$DOT</span> "
            done
            tag=""; [ "$n" = "$CUR" ] && tag=" (current)"
            rows+=$(printf '%-12s %s%s' "$n" "$sw" "$tag")$'\n'
        done
        sel=$(printf '%s' "$rows" | rofi -dmenu -i -markup-rows -p "Theme" \
            -theme "$HOME/.config/rofi/theme/picker.rasi") || exit 0
        CMD=$(sed 's/<[^>]*>//g' <<< "$sel" | awk '{print $1; exit}')
        [ -n "$CMD" ] || exit 0 ;;
    cycle)
        CMD=${THEMES[0]}
        for i in "${!THEMES[@]}"; do
            [ "${THEMES[$i]}" = "$CUR" ] && CMD=${THEMES[$(( (i + 1) % ${#THEMES[@]} ))]}
        done ;;
    restore) CMD="$CUR" ;;
esac

PAL="$T/palettes/$CMD.pal"
[ -f "$PAL" ] || { echo "Unknown theme: $CMD" >&2; exit 1; }
RELOAD=1; [ "${1:-}" = "restore" ] && RELOAD=0

# shellcheck disable=SC1090
source "$PAL"

# Build sed script from palette (hex colors only).
SEDS=()
while IFS='=' read -r k v; do
    [[ "$v" =~ ^[0-9a-f]{6}$ ]] || continue
    SEDS+=(-e "s/@@${k}@@/#${v}/g" -e "s/@@${k}_hex@@/${v}/g")
    r=$((16#${v:0:2})); g=$((16#${v:2:2})); b=$((16#${v:4:2}))
    SEDS+=(-e "s/@@${k}_rgb@@/${r}, ${g}, ${b}/g")
done < "$PAL"

render() { # template dest
    mkdir -p "$(dirname "$2")"
    sed "${SEDS[@]}" "$T/templates/$1" > "$2.tmp" && mv "$2.tmp" "$2"
}

render waybar.css     "$HOME/.config/waybar/colors/catppuccin.css"
render swaync.css     "$HOME/.config/swaync/colors/catppuccin.css"
render rofi.rasi      "$HOME/.config/rofi/colors/catppuccin.rasi"
render kitty.conf     "$HOME/.config/kitty/theme.conf"
render hyprlock.conf  "$HOME/.config/hypr/hyprlock-colors.conf"
render wlogout.css    "$HOME/.config/wlogout/colors.css"
render rofi-picker.rasi "$HOME/.config/rofi/theme/picker.rasi"
render satty.toml    "$HOME/.config/satty/config.toml"
render hypr.lua       "$HOME/.config/hypr/modules/theme.lua"

# GTK 3/4: settings.ini + libadwaita css links
for v in 3.0 4.0; do
    ini="$HOME/.config/gtk-$v/settings.ini"
    [ -f "$ini" ] || continue
    sed -i -e "s|^gtk-theme-name=.*|gtk-theme-name=$GTK|" \
           -e "s|^gtk-icon-theme-name=.*|gtk-icon-theme-name=$ICON|" \
           -e "s|^gtk-application-prefer-dark-theme=.*|gtk-application-prefer-dark-theme=$DARK|" "$ini"
done
G4="$HOME/.config/gtk-4.0"
if [ -d "/usr/share/themes/$GTK/gtk-4.0" ]; then
    for f in assets gtk.css gtk-dark.css; do
        [ -e "/usr/share/themes/$GTK/gtk-4.0/$f" ] && ln -sfn "/usr/share/themes/$GTK/gtk-4.0/$f" "$G4/$f"
    done
fi

echo "$CMD" > "$STATE/current"

scheme=prefer-dark; [ "$DARK" = 0 ] && scheme=prefer-light
gsettings set org.gnome.desktop.interface color-scheme "$scheme" 2>/dev/null
gsettings set org.gnome.desktop.interface gtk-theme "$GTK" 2>/dev/null
gsettings set org.gnome.desktop.interface icon-theme "$ICON" 2>/dev/null

if [ "$RELOAD" = 1 ]; then
    pkill -USR1 -x kitty 2>/dev/null
    hyprctl reload >/dev/null 2>&1
    "$HOME/.config/waybar/scripts/launch.sh" >/dev/null 2>&1 &
    notify-send -a theme -i preferences-desktop-theme "Theme: $CMD" "Waybar, swaync, rofi, kitty, hyprlock, borders, GTK updated" 2>/dev/null
fi
exit 0
