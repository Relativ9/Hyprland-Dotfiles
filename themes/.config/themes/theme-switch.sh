#!/bin/bash
# Theme switcher.
#   theme-switch.sh <slug>          apply a flavour by file name, e.g. mocha, tokyo-storm
#   theme-switch.sh pick            two-level rofi picker: family, then flavour (Esc goes back)
#   theme-switch.sh restore         re-render the saved theme (no reload)
#   theme-switch.sh cycle           next flavour in list
#   theme-switch.sh families        list families with flavour counts (no UI)
#   theme-switch.sh flavours <fam>  list the slugs in a family (no UI)
#
# Each palette has FAMILY= and FLAVOUR= for the picker; the saved state and wallpaper
# folders use the flat slug (file name) so nothing else depends on the grouping.
#
# Renders templates/* (placeholders like @@base@@) into each app's generated
# color file, then reloads whatever can be reloaded live.

set -uo pipefail

T="$HOME/.config/themes"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/theme"
mapfile -t THEMES < <(cd "$T/palettes" && ls *.pal | sed "s/\.pal$//")
mkdir -p "$STATE"

# pal_field <slug> <FIELD> -> value of FIELD in that palette (quotes removed)
pal_field() { grep -m1 "^$2=" "$T/palettes/$1.pal" | cut -d= -f2- | tr -d '"'; }
# flavours_of <family> -> slugs in that family, one per line
flavours_of() { for n in "${THEMES[@]}"; do [ "$(pal_field "$n" FAMILY)" = "$1" ] && echo "$n"; done; }
mapfile -t FAMILIES < <(for n in "${THEMES[@]}"; do pal_field "$n" FAMILY; done | sort -u)

CMD="${1:-pick}"
CUR=$(cat "$STATE/current" 2>/dev/null || echo macchiato)

# Two-level picker. Level 1: families (with flavour counts). Level 2: flavours of that family.
# A family with a single flavour applies straight away. Esc on level 2 returns to level 1,
# Esc on level 1 cancels (returns 1). rofi -format i returns the row index, so no text parsing.
pick_theme() {
    local DOT cur_fam fam idx s flav sw c v tag rows
    local -a slugs
    DOT=$(printf '\xe2\x97\x8f')
    cur_fam=$(pal_field "$CUR" FAMILY)
    while :; do
        rows=""
        for fam in "${FAMILIES[@]}"; do
            tag=""; [ "$fam" = "$cur_fam" ] && tag=" (current)"
            rows+="$fam ($(flavours_of "$fam" | wc -l))$tag"$'\n'
        done
        idx=$(printf '%s' "$rows" | rofi -dmenu -i -format i -p "Family" \
            -theme "$HOME/.config/rofi/theme/picker.rasi") || return 1
        [ -n "$idx" ] || return 1
        fam="${FAMILIES[$idx]}"

        mapfile -t slugs < <(flavours_of "$fam")
        if [ "${#slugs[@]}" -eq 1 ]; then
            CMD="${slugs[0]}"; return 0
        fi

        rows=""
        for s in "${slugs[@]}"; do
            flav=$(pal_field "$s" FLAVOUR); sw=""
            for c in base lavender mauve blue green yellow peach red; do
                v=$(pal_field "$s" "$c")
                sw+="<span foreground='#$v'>$DOT</span> "
            done
            tag=""; [ "$s" = "$CUR" ] && tag=" (current)"
            rows+=$(printf '%-14s %s%s' "$flav" "$sw" "$tag")$'\n'
        done
        idx=$(printf '%s' "$rows" | rofi -dmenu -i -markup-rows -format i -p "$fam" \
            -theme "$HOME/.config/rofi/theme/picker.rasi") || continue
        [ -n "$idx" ] || continue
        CMD="${slugs[$idx]}"; return 0
    done
}

case "$CMD" in
    pick)
        pick_theme || exit 0 ;;
    families)
        for fam in "${FAMILIES[@]}"; do echo "$fam ($(flavours_of "$fam" | wc -l))"; done; exit 0 ;;
    flavours)
        flavours_of "${2:?family name}"; exit 0 ;;
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
    # switch the wallpaper to one from this theme's folder (in the background, it crops to fit)
    "$HOME/.config/themes/wallpaper-for-theme.sh" "$CMD" >/dev/null 2>&1 &
    pkill -USR1 -x kitty 2>/dev/null
    hyprctl reload >/dev/null 2>&1
    "$HOME/.config/waybar/scripts/launch.sh" >/dev/null 2>&1 &
    notify-send -a theme -i preferences-desktop-theme "Theme: $CMD" "Waybar, swaync, rofi, kitty, hyprlock, borders, GTK updated" 2>/dev/null
fi
exit 0
