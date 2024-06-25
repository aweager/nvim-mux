#!/bin/zsh

source "$(dirname "$(whence -p mux)")/../lib/executor-lib.zsh"

export MUX_SESSION_ID="s:"
typeset -ga all_info_keys=(icon icon_color title title_style)

function .get() {
    setopt local_options err_return

    printf 'get\n%s' "${(F)argv}" | .nvim-comm
}

function .resolve() {
    setopt local_options err_return

    printf 'resolve\n%s' "${(F)argv}" | .nvim-comm
}

function .set() {
    setopt local_options err_return

    { printf 'set\n%s\n' "${(F)argv}"; cat } | .nvim-comm
}

function .list() {
    setopt local_options err_return

    printf 'list\n%s' "${(F)argv}" | .nvim-comm
}

function .list-parents() {
    setopt local_options err_return

    echo 'list_parents' | .nvim-comm
}

function .nvim-comm() {
    zsocket "$NVIM_IPC_SOCKET"
    local conn_fd="$REPLY"

    {
        cat >&$conn_fd
        printf '\0' >&$conn_fd

        local status_code
        read -u $conn_fd status_code

        if [[ "$status_code" == 0 ]]; then
            cat <&$conn_fd || true
        else
            cat <&$conn_fd >&2 || true
        fi

        return $status_code
    } always {
        exec {conn_fd}>&-
    }
}
