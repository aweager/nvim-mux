# Source (.) this file to set $MUX_LOCATION

# TODO: find a way to set this from neovim so it applies to non-shell panes
if [ "$MUX_TYPE" = "nvim" ] && [ -z "$MUX_LOCATION" ]; then
    MUX_LOCATION="pid:$$"
    export MUX_LOCATION
fi
